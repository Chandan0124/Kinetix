"""
Unit tests for core.sms_exporter.
Tests parsing of Android content query outputs, XML formatting for SMS Backup & Restore,
and standalone HTML viewer generation.
"""

import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from core.sms_exporter import SmsExporter


class TestSmsExporter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hypersync_test_sms_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_sms_content_query(self):
        """Tests parsing raw adb content query SMS output with tricky commas and newlines."""
        raw_output = (
            "Row: 0 _id=101, thread_id=1, address=+1555001, person=Alice, "
            "date=1698234567000, type=1, body=Hello Alice, how are you?, read=1, status=-1\n"
            "Row: 1 _id=102, thread_id=1, address=+1555001, person=Alice, "
            "date=1698234600000, type=2, body=Line 1\nLine 2 with, comma!, read=1, status=-1\n"
            "Row: 2 _id=103, thread_id=2, address=+1555002, person=null, "
            "date=1698234700000, type=1, body=Important <alert> & \"notice\", read=0, status=-1\n"
        )

        messages = SmsExporter.parse_sms_query(raw_output)
        self.assertEqual(len(messages), 3)

        # Message 1
        self.assertEqual(messages[0]["_id"], "101")
        self.assertEqual(messages[0]["address"], "+1555001")
        self.assertEqual(messages[0]["person"], "Alice")
        self.assertEqual(messages[0]["body"], "Hello Alice, how are you?")
        self.assertEqual(messages[0]["type"], 1)

        # Message 2 (multiline and comma in body)
        self.assertEqual(messages[1]["_id"], "102")
        self.assertEqual(messages[1]["type"], 2)
        self.assertIn("Line 1\nLine 2 with, comma!", messages[1]["body"])

        # Message 3 (null person and special chars)
        self.assertEqual(messages[2]["_id"], "103")
        self.assertIsNone(messages[2]["person"])
        self.assertEqual(messages[2]["body"], 'Important <alert> & "notice"')
        self.assertEqual(messages[2]["read"], 0)

    def test_parse_call_query(self):
        """Tests parsing raw adb content query call logs output."""
        raw_output = (
            "Row: 0 _id=1, number=+1555001, date=1698230000000, duration=135, type=1, name=Alice\n"
            "Row: 1 _id=2, number=+1555999, date=1698231000000, duration=0, type=3, name=null\n"
        )

        calls = SmsExporter.parse_call_query(raw_output)
        self.assertEqual(len(calls), 2)

        # Call 1
        self.assertEqual(calls[0]["_id"], "1")
        self.assertEqual(calls[0]["number"], "+1555001")
        self.assertEqual(calls[0]["duration"], 135)
        self.assertEqual(calls[0]["type"], 1)
        self.assertEqual(calls[0]["name"], "Alice")
        self.assertEqual(calls[0]["duration_formatted"], "2m 15s")

        # Call 2 (Missed)
        self.assertEqual(calls[1]["type"], 3)
        self.assertEqual(calls[1]["duration"], 0)
        self.assertEqual(calls[1]["duration_formatted"], "0s")

    def test_generate_sms_xml_schema(self):
        """Tests that generated XML adheres to SMS Backup & Restore schema and parses validly."""
        messages = [
            {
                "_id": "1",
                "address": "+1555001",
                "person": "Alice Smith",
                "date": 1698234567000,
                "readable_date": "Oct 25, 2023 10:02:47 AM",
                "type": 1,
                "body": 'Hello <world> & "friends"!',
                "read": 1,
                "status": "-1",
            },
            {
                "_id": "2",
                "address": "+1555002",
                "person": None,
                "date": 1698234600000,
                "readable_date": "Oct 25, 2023 10:03:20 AM",
                "type": 2,
                "body": "Outgoing message response",
                "read": 1,
                "status": "-1",
            },
        ]

        xml_file = Path(self.temp_dir) / "sms_backup.xml"
        SmsExporter.generate_sms_xml(messages, xml_file)

        self.assertTrue(xml_file.is_file())

        # Validate with ElementTree parser
        tree = ET.parse(xml_file)
        root = tree.getroot()

        self.assertEqual(root.tag, "smses")
        self.assertEqual(root.attrib["count"], "2")

        sms_elements = list(root.findall("sms"))
        self.assertEqual(len(sms_elements), 2)

        # First element verification
        el1 = sms_elements[0]
        self.assertEqual(el1.attrib["address"], "+1555001")
        self.assertEqual(el1.attrib["type"], "1")
        self.assertEqual(el1.attrib["body"], 'Hello <world> & "friends"!')
        self.assertEqual(el1.attrib["contact_name"], "Alice Smith")

        # Second element verification
        el2 = sms_elements[1]
        self.assertEqual(el2.attrib["address"], "+1555002")
        self.assertEqual(el2.attrib["type"], "2")
        self.assertEqual(el2.attrib["body"], "Outgoing message response")

    def test_generate_calls_xml_schema(self):
        """Tests that calls XML is correctly formed and parses validly."""
        calls = [
            {
                "_id": "1",
                "number": "+1555123",
                "date": 1698234567000,
                "duration": 45,
                "type": 2,
                "name": "Bob",
                "readable_date": "Oct 25, 2023 10:00:00 AM",
            }
        ]

        xml_file = Path(self.temp_dir) / "calls_backup.xml"
        SmsExporter.generate_calls_xml(calls, xml_file)

        tree = ET.parse(xml_file)
        root = tree.getroot()
        self.assertEqual(root.tag, "calls")
        self.assertEqual(root.attrib["count"], "1")

        call_el = root.find("call")
        self.assertIsNotNone(call_el)
        self.assertEqual(call_el.attrib["number"], "+1555123")
        self.assertEqual(call_el.attrib["duration"], "45")
        self.assertEqual(call_el.attrib["type"], "2")

    def test_generate_html_viewer(self):
        """Tests that generated standalone HTML contains responsive UI and embedded JSON scripts."""
        messages = [
            {
                "_id": "1",
                "address": "+1555100",
                "person": "Charlie",
                "date": 1698234567000,
                "readable_date": "Oct 25, 2023 10:00:00 AM",
                "type": 1,
                "body": "Hey there Charlie",
                "read": 1,
                "status": "-1",
            }
        ]
        calls = [
            {
                "_id": "10",
                "number": "+1555100",
                "date": 1698234500000,
                "duration": 60,
                "duration_formatted": "1m 0s",
                "type": 1,
                "name": "Charlie",
                "readable_date": "Oct 25, 2023 09:59:00 AM",
            }
        ]

        html_file = Path(self.temp_dir) / "sms_viewer.html"
        SmsExporter.generate_html_viewer(messages, calls, html_file)

        self.assertTrue(html_file.is_file())
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check key components
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn('id="sms-data" type="application/json"', content)
        self.assertIn('id="call-data" type="application/json"', content)
        self.assertIn("Hey there Charlie", content)
        self.assertIn("MobilePCSync Archive", content)
        self.assertIn("filterThreads()", content)
        self.assertIn("chat-pane", content)
        self.assertIn("call-view", content)


if __name__ == "__main__":
    unittest.main()
