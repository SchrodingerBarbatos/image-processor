import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from PIL import Image

import barcode_image_mover_exe as app


class MemoryLog:
    def __init__(self):
        self.lines = []

    def write(self, msg, end='\n'):
        self.lines.append(msg)


class CoreRegressionTests(unittest.TestCase):
    def test_validate_output_dir_rejects_same_or_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'src')
            os.makedirs(source)
            with self.assertRaises(ValueError):
                app.validate_output_dir(source, source)
            with self.assertRaises(ValueError):
                app.validate_output_dir(source, os.path.join(source, 'out'))
            with self.assertRaises(ValueError):
                app.validate_output_dir(source, tmp)
            app.validate_output_dir(source, os.path.join(tmp, 'out'))

    def test_suggest_output_dir_is_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'images')
            os.makedirs(source)
            suggested = app.suggest_output_dir(source)
            self.assertEqual(suggested, os.path.join(tmp, 'images_输出'))

    def test_unique_preserve_order_counts_duplicates(self):
        unique, dup = app.unique_preserve_order(['A', 'B', 'A', 'C', 'B', ''])
        self.assertEqual(unique, ['A', 'B', 'C', ''])
        self.assertEqual(dup, 2)

    def test_log_writer_thread_safe_writes_all_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'log.txt')
            writer = app.LogWriter(path)

            def write_many(prefix):
                for i in range(100):
                    writer.write(f'{prefix}-{i}')

            with redirect_stdout(StringIO()):
                threads = [threading.Thread(target=write_many, args=(f't{n}',)) for n in range(6)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                writer.close()

            with open(path, encoding='utf-8') as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 600)
            self.assertTrue(all(line.startswith('[') and '] t' in line for line in lines))

    def test_log_writer_writes_complete_lines_to_stdout(self):
        class CapturingStdout:
            def __init__(self):
                self.calls = []

            def write(self, text):
                self.calls.append(text)

            def flush(self):
                pass

        stdout = CapturingStdout()
        with patch('sys.stdout', stdout):
            writer = app.LogWriter()
            writer.write('one line')
            writer.close()

        self.assertEqual(len(stdout.calls), 1)
        self.assertIn('one line', stdout.calls[0])
        self.assertTrue(stdout.calls[0].endswith('\n'))

    def test_log_writer_open_failure_does_not_abort_logging(self):
        with patch('app.services.logger.open', side_effect=OSError('nope')):
            with redirect_stdout(StringIO()) as stdout:
                writer = app.LogWriter('bad/log.txt')
                writer.write('still logs')
                writer.close()

        text = stdout.getvalue()
        self.assertIn('[警告] 日志文件无法创建', text)
        self.assertIn('still logs', text)

    def test_log_writer_keeps_gui_callback_compatibility_on_main_thread(self):
        seen = []
        with redirect_stdout(StringIO()):
            writer = app.LogWriter(gui_callback=seen.append)
            writer.write('hello gui')
            writer.close()

        self.assertEqual(len(seen), 1)
        self.assertIn('hello gui', seen[0])

    def test_log_writer_does_not_call_gui_callback_from_worker_thread(self):
        seen = []
        with redirect_stdout(StringIO()):
            writer = app.LogWriter(gui_callback=seen.append)
            thread = threading.Thread(target=lambda: writer.write('worker log'))
            thread.start()
            thread.join()
            writer.close()

        self.assertEqual(seen, [])

    def test_run_all_clears_reserved_paths_after_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'src')
            output = os.path.join(tmp, 'out')
            os.makedirs(source)
            Image.new('RGB', (10, 10), 'red').save(os.path.join(source, 'a.jpg'))

            def reserve_then_fail(*args, **kwargs):
                app.get_unique_path(os.path.join(output, 'reserved.jpg'), reserve=True)
                raise RuntimeError('boom')

            with patch('barcode_image_mover_exe.step1_detail', side_effect=reserve_then_fail):
                with redirect_stdout(StringIO()):
                    app.run_all(source, output, mode=4)

        self.assertEqual(app._RESERVED_OUTPUT_PATHS, set())

    def test_copy_files_parallel_counts_completed_files_after_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'src')
            output = os.path.join(tmp, 'out')
            os.makedirs(source)
            for name in ('a.jpg', 'b.jpg'):
                with open(os.path.join(source, name), 'wb') as f:
                    f.write(name.encode())

            stop_event = threading.Event()
            original_copy2 = app.shutil.copy2

            def copy_and_stop(src, dst):
                result = original_copy2(src, dst)
                stop_event.set()
                return result

            with patch('app.core.file_ops.COPY_WORKERS', 1):
                with patch('app.core.file_ops.shutil.copy2', side_effect=copy_and_stop):
                    copied = app.copy_files_parallel(
                        source, output, ['a.jpg', 'b.jpg'], MemoryLog(), '测试', stop_event
                    )

            self.assertEqual(copied, 1)
            self.assertTrue(os.path.exists(os.path.join(output, 'a.jpg')))

    def test_zip_logs_file_larger_than_split_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'src')
            target = os.path.join(tmp, 'zips')
            os.makedirs(source)
            with open(os.path.join(source, 'big.jpg'), 'wb') as f:
                f.write(b'x' * 2048)
            log = MemoryLog()

            app.step8_zip(source, target, 1000, log)

            self.assertTrue(any('超过分卷上限' in line for line in log.lines))

    def test_zip_uses_deflated_compression(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'src')
            target = os.path.join(tmp, 'zips')
            os.makedirs(source)
            with open(os.path.join(source, 'compressible.jpg'), 'wb') as f:
                f.write(b'x' * 2048)

            app.step8_zip(source, target, 10000, MemoryLog())

            zips = [name for name in os.listdir(target) if name.endswith('.zip')]
            self.assertEqual(len(zips), 1)
            import zipfile
            with zipfile.ZipFile(os.path.join(target, zips[0])) as zf:
                self.assertEqual(zf.infolist()[0].compress_type, zipfile.ZIP_DEFLATED)

    def test_excel_auto_end_scans_rows_even_when_max_row_is_wrong(self):
        class FakeSheet:
            max_row = 1

            def iter_rows(self, min_row=None, max_row=None, min_col=None, max_col=None, values_only=None):
                yield ('SKU-1',)
                yield ('SKU-2',)
                for _ in range(app.EXCEL_EMPTY_ROW_BREAK_THRESHOLD):
                    yield (None,)

        class FakeWorkbook:
            sheetnames = ['Sheet1']

            def __init__(self):
                self.active = FakeSheet()

            def close(self):
                pass

        with tempfile.NamedTemporaryFile(suffix='.xlsx') as fake_excel:
            with patch('openpyxl.load_workbook', return_value=FakeWorkbook()):
                barcodes = app.step3_read_excel(fake_excel.name, 'A', MemoryLog())

        self.assertEqual(barcodes, ['SKU-1', 'SKU-2'])

    def test_preview_match_works_without_output_dirs(self):
        log = MemoryLog()
        files = ['A_详情图.jpg', 'B_详情图.png', 'A.jpg']
        app.step4_match_preview(files, ['A', 'C'], log, clean_detail_name=True)
        text = "\n".join(log.lines)
        self.assertIn('[预览] A_详情图.jpg', text)
        self.assertIn('未匹配1个条码', text)

    def test_preview_match_case_insensitive(self):
        log = MemoryLog()
        files = ['sku-a_详情图.jpg', 'SKU-B.jpg']
        app.step4_match_preview(files, ['SKU-A', 'sku-b'], log, clean_detail_name=True)
        text = "\n".join(log.lines)
        self.assertIn('[预览] sku-a_详情图.jpg', text)
        self.assertIn('[预览] SKU-B.jpg', text)

    def test_parallel_image_processing_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            main_dir = os.path.join(tmp, 'main')
            detail_dir = os.path.join(tmp, 'detail')
            os.makedirs(main_dir)
            os.makedirs(detail_dir)
            Image.new('RGB', (120, 80), 'red').save(os.path.join(main_dir, 'main.bmp'))
            Image.new('RGB', (80, 120), 'blue').save(os.path.join(detail_dir, 'detail.bmp'))
            log = MemoryLog()

            app.step6_process_main(main_dir, log, resize_mode='fit', force_format='jpg')
            app.step7_process_detail(detail_dir, log, force_format='jpg')

            self.assertTrue(any(name.lower().endswith(('.jpg', '.png')) for name in os.listdir(main_dir)))
            self.assertTrue(any(name.lower().endswith('.jpg') for name in os.listdir(detail_dir)))

    def test_process_main_image_old_file_delete_failure_is_warning_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            main_dir = os.path.join(tmp, 'main')
            os.makedirs(main_dir)
            src_name = 'sample.bmp'
            src_path = os.path.join(main_dir, src_name)
            Image.new('RGB', (120, 80), 'red').save(src_path)

            real_remove = app.os.remove

            def remove_with_old_file_failure(path):
                if os.path.normcase(path) == os.path.normcase(src_path):
                    raise OSError('locked')
                return real_remove(path)

            with patch('barcode_image_mover_exe.os.remove', side_effect=remove_with_old_file_failure):
                result = app._process_main_image(main_dir, src_name, force_format='jpg')

            self.assertTrue(result.ok)
            self.assertIsNone(result.error)
            self.assertTrue(result.filename.lower().endswith('.jpg'))
            self.assertTrue(os.path.exists(os.path.join(main_dir, result.filename)))

    def test_process_main_image_returns_named_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            main_dir = os.path.join(tmp, 'main')
            os.makedirs(main_dir)
            src_name = 'sample.jpg'
            Image.new('RGB', (800, 800), 'red').save(os.path.join(main_dir, src_name))

            result = app._process_main_image(main_dir, src_name)

            self.assertEqual(result.filename, src_name)
            self.assertTrue(result.ok)
            self.assertIsNone(result.error)
            self.assertIsNone(result.manual_copy)

    def test_process_main_image_copies_source_original_to_manual_dir_when_still_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = os.path.join(tmp, 'source')
            main_dir = os.path.join(tmp, 'main')
            manual_dir = os.path.join(tmp, 'manual')
            os.makedirs(source_dir)
            os.makedirs(main_dir)
            src_name = 'too_big.jpg'
            source_path = os.path.join(source_dir, src_name)
            work_path = os.path.join(main_dir, src_name)
            Image.new('RGB', (20, 20), 'red').save(source_path)
            Image.new('RGB', (20, 20), 'blue').save(work_path)
            with open(source_path, 'rb') as f:
                original_bytes = f.read()
            source_lookup = app.build_manual_source_lookup(source_dir, [src_name])

            with patch('barcode_image_mover_exe.MAIN_IMAGE_MAX_BYTES', 1):
                result = app._process_main_image(
                    main_dir, src_name, manual_dir=manual_dir, manual_source_lookup=source_lookup
                )

            self.assertTrue(result.ok)
            self.assertIsNone(result.error)
            self.assertIsNotNone(result.manual_copy)
            manual_path = os.path.join(manual_dir, src_name)
            self.assertTrue(os.path.exists(manual_path))
            with open(manual_path, 'rb') as f:
                self.assertEqual(f.read(), original_bytes)

    def test_process_main_image_keeps_standard_png_when_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = os.path.join(tmp, 'source')
            main_dir = os.path.join(tmp, 'main')
            manual_dir = os.path.join(tmp, 'manual')
            os.makedirs(source_dir)
            os.makedirs(main_dir)
            src_name = 'standard.png'
            source_path = os.path.join(source_dir, src_name)
            work_path = os.path.join(main_dir, src_name)
            Image.effect_noise((600, 600), 100).convert('RGB').save(source_path, 'PNG')
            Image.effect_noise((600, 600), 100).convert('RGB').save(work_path, 'PNG')
            source_lookup = app.build_manual_source_lookup(source_dir, [src_name])

            with patch('barcode_image_mover_exe.MAIN_IMAGE_MAX_BYTES', 20_000):
                result = app._process_main_image(
                    main_dir, src_name, force_format='png',
                    manual_dir=manual_dir, manual_source_lookup=source_lookup
                )

            self.assertTrue(result.ok)
            self.assertIsNone(result.error)
            self.assertEqual(result.filename, src_name)
            self.assertIsNotNone(result.manual_copy)
            self.assertTrue(os.path.exists(os.path.join(manual_dir, src_name)))
            self.assertFalse(any(name.lower().endswith(('.jpg', '.jpeg')) for name in os.listdir(main_dir)))

    def test_process_detail_image_copies_source_original_after_detail_rename_when_still_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = os.path.join(tmp, 'source')
            detail_dir = os.path.join(tmp, 'detail')
            manual_dir = os.path.join(tmp, 'manual')
            os.makedirs(source_dir)
            os.makedirs(detail_dir)
            source_name = 'too_big_详情图.bmp'
            work_name = app.clean_detail_suffix(source_name)
            source_path = os.path.join(source_dir, source_name)
            work_path = os.path.join(detail_dir, work_name)
            Image.new('RGB', (20, 20), 'red').save(source_path)
            Image.new('RGB', (20, 20), 'blue').save(work_path)
            with open(source_path, 'rb') as f:
                original_bytes = f.read()
            source_lookup = app.build_manual_source_lookup(source_dir, [source_name], clean_detail_name=True)

            with patch('barcode_image_mover_exe.DETAIL_IMAGE_MAX_BYTES', 1):
                result = app._process_detail_image(
                    detail_dir, work_name, manual_dir=manual_dir, manual_source_lookup=source_lookup
                )

            self.assertTrue(result.ok)
            self.assertIsNone(result.error)
            self.assertIsNotNone(result.manual_copy)
            manual_path = os.path.join(manual_dir, source_name)
            self.assertTrue(os.path.exists(manual_path))
            with open(manual_path, 'rb') as f:
                self.assertEqual(f.read(), original_bytes)

    def test_process_detail_image_keeps_standard_png_when_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = os.path.join(tmp, 'source')
            detail_dir = os.path.join(tmp, 'detail')
            manual_dir = os.path.join(tmp, 'manual')
            os.makedirs(source_dir)
            os.makedirs(detail_dir)
            src_name = 'standard.png'
            source_path = os.path.join(source_dir, src_name)
            work_path = os.path.join(detail_dir, src_name)
            Image.effect_noise((600, 600), 100).convert('RGB').save(source_path, 'PNG')
            Image.effect_noise((600, 600), 100).convert('RGB').save(work_path, 'PNG')
            source_lookup = app.build_manual_source_lookup(source_dir, [src_name])

            with patch('barcode_image_mover_exe.DETAIL_IMAGE_MAX_BYTES', 20_000):
                result = app._process_detail_image(
                    detail_dir, src_name, force_format=None,
                    manual_dir=manual_dir, manual_source_lookup=source_lookup
                )

            self.assertTrue(result.ok)
            self.assertIsNone(result.error)
            self.assertEqual(result.filename, src_name)
            self.assertEqual(result.converted, 0)
            self.assertIsNotNone(result.manual_copy)
            self.assertTrue(os.path.exists(os.path.join(manual_dir, src_name)))
            self.assertFalse(any(name.lower().endswith(('.jpg', '.jpeg')) for name in os.listdir(detail_dir)))

    def test_process_detail_image_returns_named_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            detail_dir = os.path.join(tmp, 'detail')
            os.makedirs(detail_dir)
            src_name = 'detail.jpg'
            Image.new('RGB', (20, 20), 'red').save(os.path.join(detail_dir, src_name))

            result = app._process_detail_image(detail_dir, src_name)

            self.assertEqual(result.filename, src_name)
            self.assertTrue(result.ok)
            self.assertIsNone(result.error)
            self.assertEqual(result.converted, 0)
            self.assertEqual(result.compressed, 0)
            self.assertIsNone(result.info)
            self.assertIsNone(result.manual_copy)

    def test_step4_match_returns_actual_output_to_source_mapping_for_duplicate_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'source')
            output = os.path.join(tmp, 'output')
            original = os.path.join(tmp, 'original')
            os.makedirs(source)
            os.makedirs(original)

            first_name = 'SKU_详情图.jpg'
            second_name = 'SKU.jpg'
            for folder in (source, original):
                Image.new('RGB', (10, 10), 'red').save(os.path.join(folder, first_name))
                Image.new('RGB', (10, 10), 'blue').save(os.path.join(folder, second_name))
            source_lookup = app.build_manual_source_lookup(original, [first_name, second_name], clean_detail_name=True)

            output_lookup = app.step4_match(
                source, output, ['SKU'], MemoryLog(),
                clean_detail_name=True, copy_mode=True,
                manual_source_lookup=source_lookup
            )

            self.assertTrue(os.path.exists(os.path.join(output, 'SKU.jpg')))
            self.assertTrue(os.path.exists(os.path.join(output, 'SKU_dup1.jpg')))
            self.assertEqual(
                output_lookup[os.path.normcase('SKU.jpg')],
                os.path.join(original, second_name)
            )
            self.assertEqual(
                output_lookup[os.path.normcase('SKU_dup1.jpg')],
                os.path.join(original, first_name)
            )

    def test_mode_name_matches_ui_text_for_classify_only(self):
        self.assertEqual(app.MODE_NAMES[4], '仅分类(无Excel)')

    def test_zip_entry_paths_use_forward_slashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'source')
            nested = os.path.join(source, 'nested')
            target = os.path.join(tmp, 'zips')
            os.makedirs(nested)
            os.makedirs(target)
            Image.new('RGB', (10, 10), 'red').save(os.path.join(nested, 'a.jpg'))

            app.step8_zip(source, target, app.ZIP_SPLIT_BYTES, MemoryLog())

            import zipfile
            zip_path = os.path.join(target, 'source_001.zip')
            with zipfile.ZipFile(zip_path) as zf:
                self.assertEqual(zf.namelist(), ['nested/a.jpg'])


if __name__ == '__main__':
    unittest.main()
