# -*- coding: utf-8 -*-
"""target 列格式校验与保存逻辑的单元测试。"""

import codecs
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from translator_gui import (  # noqa: E402
    build_rows,
    replace_target_texts,
    save_file,
    validate_target,
)
from EO5.checker import check_reverted_entry as eo5_checker  # noqa: E402
from EO5.single_parser import parse_single_entry as eo5_parse  # noqa: E402
from checker import check_reverted_entry as eou2_checker  # noqa: E402


class ValidateTargetTests(unittest.TestCase):
    def test_clean_target_passes(self):
        text = '{f859}{0100}こんにちは{f801}{f804}{0000}'
        self.assertEqual(validate_target(text, eo5_checker), [])

    def test_f859_missing_id_flagged(self):
        issues = validate_target('{f859}こんにちは{f801}', eo5_checker)
        self.assertTrue(any('f859' in issue for issue in issues))

    def test_f859_bad_id_chars_flagged(self):
        issues = validate_target('{f859}{zzzz}やあ{f801}', eo5_checker)
        self.assertTrue(any('f859' in issue for issue in issues))

    def test_leftover_placeholder_flagged(self):
        issues = validate_target('[[speaker: 洁莉妮]]こんにちは{f801}', eo5_checker)
        self.assertTrue(issues, '残留 [[ 占位符未被标记')
        self.assertIn('控制字符', issues[0])

    def test_long_row_flagged(self):
        issues = validate_target('あ' * 23 + '{f801}', eo5_checker)
        self.assertTrue(any('22' in issue or '长度' in issue for issue in issues))

    def test_eou2_checker_uses_same_rules(self):
        self.assertEqual(validate_target('{f859}{1300}やあ{f801}', eou2_checker), [])
        issues = validate_target('{f859}やあ{f801}', eou2_checker)
        self.assertTrue(any('f859' in issue for issue in issues))


class ReplaceTargetTextsTests(unittest.TestCase):
    SAMPLE = (
        '<mbm>\r\n'
        '  <entry id="0">\r\n'
        '    <source>src0</source>\r\n'
        '    <target>old0</target>\r\n'
        '  </entry>\r\n'
        '  <entry id="1">\r\n'
        '    <source>src1</source>\r\n'
        '    <target/>\r\n'
        '  </entry>\r\n'
        '  <entry id="2">\r\n'
        '    <source>src2</source>\r\n'
        '  </entry>\r\n'
        '</mbm>\r\n'
    )

    def test_replace_preserves_format_and_escapes(self):
        out = replace_target_texts(self.SAMPLE, ['new&<0>', 'new1', 'new2'])
        self.assertIn('<target>new&amp;&lt;0&gt;</target>', out)
        self.assertIn('<target>new1</target>', out)
        self.assertIn('<target>new2</target>', out)
        self.assertIn('    <source>src0</source>', out)
        self.assertTrue(out.startswith('<mbm>'))
        self.assertTrue(out.endswith('</mbm>\r\n'))
        self.assertEqual(out.count('<source>'), 3)
        order = [
            out.index('<target>new&amp;&lt;0&gt;</target>'),
            out.index('<target>new1</target>'),
            out.index('<target>new2</target>'),
        ]
        self.assertEqual(order, sorted(order))

    def test_count_mismatch_raises(self):
        with self.assertRaises(ValueError):
            replace_target_texts(self.SAMPLE, ['a', 'b'])


class BuildRowsTests(unittest.TestCase):
    def test_build_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'test.xml'
            p.write_text(
                '<mbm>'
                '<entry id="1"><source>こんにちは{f801}</source>'
                '<target>やあ{f801}</target></entry>'
                '<entry id="2"><source>src2</source></entry>'
                '</mbm>',
                encoding='utf-8',
            )
            rows = build_rows(p, eo5_parse)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['entry_id'], '1')
            self.assertEqual(rows[0]['source'], 'こんにちは[[换行]]')
            self.assertEqual(rows[0]['translation'], 'やあ[[换行]]')
            self.assertEqual(rows[0]['target'], 'やあ{f801}')
            self.assertEqual(rows[1]['target'], '')


class SaveFileTests(unittest.TestCase):
    def test_save_roundtrip_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'test.xml'
            raw = (
                '<mbm>\r\n'
                '  <entry id="0">\r\n'
                '    <source>s0</source>\r\n'
                '    <target>old0</target>\r\n'
                '  </entry>\r\n'
                '</mbm>\r\n'
            )
            p.write_bytes(raw.encode('utf-8'))
            rows = [{'entry_id': '0', 'target': 'new0&<>{f801}'}]
            backup = save_file(p, rows)
            self.assertTrue(Path(backup).is_file())
            self.assertEqual(
                p.read_bytes().decode('utf-8'),
                raw.replace('old0', 'new0&amp;&lt;&gt;{f801}'),
            )
            tree = ET.parse(p)
            self.assertEqual(tree.getroot()[0].find('target').text, 'new0&<>{f801}')

    def test_save_preserves_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'test.xml'
            raw = (
                '<mbm>\n'
                '  <entry id="0">\n'
                '    <source>s0</source>\n'
                '    <target>t0</target>\n'
                '  </entry>\n'
                '</mbm>\n'
            )
            p.write_bytes(codecs.BOM_UTF8 + raw.encode('utf-8'))
            save_file(p, [{'entry_id': '0', 'target': 't1'}])
            data = p.read_bytes()
            self.assertTrue(data.startswith(codecs.BOM_UTF8))
            self.assertIn(b'<target>t1</target>', data)


if __name__ == '__main__':
    unittest.main()
