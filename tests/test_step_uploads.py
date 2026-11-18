import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import requests


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 18, 20, 5, tzinfo=tz)


class StepUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Module startup reads config; prevent any live network or LINE calls.
        with patch.object(requests, 'get', return_value=Mock(status_code=200, json=lambda: [])):
            spec = importlib.util.spec_from_file_location('bot_under_test', Path(__file__).parents[1] / 'bot.py')
            cls.bot = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.bot)

    def setUp(self):
        self.records = []
        self.config = {'last_daily_push': '2026-11-18'}
        self.patches = [
            patch.object(self.bot, 'datetime', Clock),
            patch.object(self.bot, '_get_config', side_effect=lambda key: self.config.get(key)),
            patch.object(self.bot, '_set_config', side_effect=self.set_config),
            patch.object(self.bot, 'db_insert_step', side_effect=self.insert),
            patch.object(self.bot, 'db_get_latest_all', side_effect=lambda date: list({r['name']: r for r in self.records}.values())),
            patch.object(self.bot.http_requests, 'get', side_effect=self.http_get),
            patch.object(self.bot, 'line_bot_api', Mock()),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.client = self.bot.app.test_client()

    def set_config(self, key, value):
        self.config[key] = value
        return True

    def insert(self, name, steps, date, time):
        self.records.append(dict(name=name, steps=steps, date=date, time=time))
        return True

    def http_get(self, *args, **kwargs):
        if args and args[0].endswith('/steps'):
            return Mock(status_code=200, json=lambda: self.records[:])
        rows = [dict(key=key, value=value) for key, value in self.config.items()
                if key.startswith('step_status:')]
        return Mock(status_code=200, json=lambda: rows)

    def payload(self, **changes):
        data = dict(name='媽媽', steps=49, step_date='2026-11-18',
                    sensor_at='2026-11-18T19:58:00+08:00', status='ok',
                    partial=False, app_version='1.0.2', device_id='test-device')
        data.update(changes)
        return data

    def test_yesterdays_snapshot_never_becomes_today(self):
        response = self.client.post('/steps', json=self.payload(
            steps=4117, step_date='2026-11-17', sensor_at='2026-11-17T16:45:00+08:00'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.records, [])

    def test_old_sensor_cannot_be_relabeled_with_todays_date(self):
        response = self.client.post('/steps', json=self.payload(sensor_at='2026-11-17T16:45:00+08:00'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.records, [])

    def test_future_and_naive_sensor_timestamps_are_rejected(self):
        for value in ('2026-11-18T23:00:00+08:00', '2026-11-18T19:58:00'):
            with self.subTest(value=value):
                self.assertEqual(self.client.post('/steps', json=self.payload(sensor_at=value)).status_code, 400)
        self.assertEqual(self.records, [])

    def test_waiting_is_visible_without_inventing_zero_steps(self):
        response = self.client.post('/steps', json=self.payload(
            steps=None, status='waiting', sensor_at='2026-11-17T16:45:00+08:00'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.records, [])
        message = self.bot.build_steps_message()
        self.assertIn('媽媽', message)
        self.assertIn('等待', message)
        self.assertNotIn('媽媽：0', message)

    def test_valid_snapshot_records_sensor_time_and_partial_status(self):
        response = self.client.post('/steps', json=self.payload(partial=True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.records, [dict(name='媽媽', steps=49, date='2026-11-18', time='19:58')])
        self.assertIn('部分', self.bot.build_steps_message())

    def test_legacy_phone_still_uploads_without_new_fields(self):
        self.assertEqual(self.client.post('/steps', json=dict(name='爸爸', steps=321)).status_code, 200)
        self.assertEqual(self.records[0]['steps'], 321)
        self.assertEqual(self.records[0]['time'], '20:05')

    def test_database_failure_is_not_reported_as_success(self):
        with patch.object(self.bot, 'db_insert_step', return_value=False):
            self.assertEqual(self.client.post('/steps', json=self.payload()).status_code, 503)

    def test_invalid_counts_and_json_objects_are_rejected(self):
        for value in (-1, True, 1.5, 'bad'):
            with self.subTest(value=value):
                self.assertEqual(self.client.post('/steps', json=self.payload(steps=value)).status_code, 400)
        self.assertEqual(self.client.post('/steps', json=['unexpected']).status_code, 400)
        self.assertEqual(self.records, [])

    def test_empty_or_nonobject_json_cannot_create_false_zero_steps(self):
        for value in ([], {}, False, None):
            with self.subTest(value=value):
                self.assertEqual(self.client.post('/steps', json=value).status_code, 400)
        self.assertEqual(self.records, [])

    def test_report_keeps_durable_partial_snapshot_when_history_is_unavailable(self):
        self.client.post('/steps', json=self.payload(partial=True))
        self.records.clear()
        self.insert('爸爸', 321, '2026-11-18', '20:00')
        message = self.bot.build_steps_message()
        self.assertIn('爸爸：321', message)
        self.assertIn('媽媽：49', message)
        self.assertIn('部分', message)

    def test_real_db_insert_checks_http_failure(self):
        self.patches[3].stop()
        with patch.object(self.bot.http_requests, 'post', return_value=Mock(status_code=500)):
            self.assertFalse(self.bot.db_insert_step('媽媽', 49, '2026-11-18', '19:58'))

    def test_metadata_failure_cannot_store_an_unlabeled_partial_point(self):
        with patch.object(self.bot, '_set_config', return_value=False):
            self.assertEqual(self.client.post('/steps', json=self.payload(partial=True)).status_code, 503)
        self.assertEqual(self.records, [])
        self.assertEqual(self.client.post('/steps', json=self.payload(partial=True)).status_code, 200)
        self.assertEqual(len(self.records), 1)
        self.assertIn('部分', self.bot.build_steps_message())

    def test_retried_observation_does_not_duplicate_numeric_history(self):
        self.client.post('/steps', json=self.payload())
        self.client.post('/steps', json=self.payload())
        self.assertEqual(len(self.records), 1)

    def test_older_delivery_cannot_replace_newer_sensor_observation(self):
        self.client.post('/steps', json=self.payload(steps=100))
        self.client.post('/steps', json=self.payload(steps=50, sensor_at='2026-11-18T19:30:00+08:00'))
        self.assertEqual(len(self.records), 1)
        self.assertIn('媽媽：100', self.bot.build_steps_message())

    def test_waiting_overrides_current_report_but_retains_partial_history(self):
        self.client.post('/steps', json=self.payload(partial=True))
        self.client.post('/steps', json=self.payload(steps=None, status='waiting', partial=False))
        message = self.bot.build_steps_message()
        self.assertIn('等待', message)
        self.assertIn('部分', message)
        self.assertEqual(len(self.records), 1)
        self.client.post('/steps', json=self.payload(steps=60, sensor_at='2026-11-18T20:00:00+08:00', partial=True))
        self.assertNotIn('等待', self.bot.build_steps_message())
        self.assertIn('媽媽：60', self.bot.build_steps_message())

    def test_completion_marker_failure_is_recovered_without_losing_quality_or_duplicating(self):
        calls = 0
        def setter(key, value):
            nonlocal calls
            calls += 1
            return False if calls == 2 else self.set_config(key, value)
        with patch.object(self.bot, '_set_config', side_effect=setter):
            self.assertEqual(self.client.post('/steps', json=self.payload(partial=True)).status_code, 200)
        self.assertIn('部分', self.bot.build_steps_message())
        self.assertEqual(self.client.post('/steps', json=self.payload(partial=True)).status_code, 200)
        self.assertEqual(len(self.records), 1)


if __name__ == '__main__':
    unittest.main()
