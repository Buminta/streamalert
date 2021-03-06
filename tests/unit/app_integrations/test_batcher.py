"""
Copyright 2017-present, Airbnb Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
# pylint: disable=protected-access
from botocore.exceptions import ClientError
from mock import patch
from nose.tools import assert_equal, assert_false, assert_true, raises

from app_integrations.batcher import Batcher
from tests.unit.app_integrations.test_helpers import MockLambdaClient


class TestAppBatcher(object):
    """Class for handling testing of the app integration output batcher"""

    def __init__(self):
        self.batcher = None

    def setup(self):
        """Setup class before tests"""
        self.batcher = Batcher({'cluster': 'cluster',
                                'prefix': 'prefix',
                                'region': 'us-east-1'})

        # Use a mocked version of the Lambda client to patch out the instance client
        Batcher.LAMBDA_CLIENT = MockLambdaClient

    @patch('logging.Logger.info')
    def test_send_logs_lambda_success(self, log_mock):
        """App Integration Batcher - Send Logs to StreamAlert, Successful"""
        log_count = 5
        logs = [{'timestamp': 'time',
                 'eventtype': 'authentication',
                 'host': 'host'} for _ in range(log_count)]

        result = self.batcher._send_logs_to_stream_alert('duo_auth', logs)

        assert_true(result)
        log_mock.assert_called_with('Sent %d logs to \'%s\' with Lambda request ID \'%s\'',
                                    log_count, 'prefix_cluster_streamalert_rule_processor',
                                    '9af88643-7b3c-43cd-baae-addb73bb4d27')

    @raises(ClientError)
    def test_send_logs_lambda_exception(self):
        """App Integration Batcher - Send Logs to StreamAlert, Exception"""
        MockLambdaClient._raise_exception = True
        logs = [{'timestamp': 'time',
                 'eventtype': 'authentication',
                 'host': 'host'}]

        self.batcher._send_logs_to_stream_alert('duo_auth', logs)

    def test_send_logs_lambda_too_large(self):
        """App Integration Batcher - Send Logs to StreamAlert, Exceeds Size"""
        # The length of the below list of logs dumped to json should exceed the
        # max AWS lambda input size of 128000 (this results in 128001)
        logs = [{'timestamp': 'time',
                 'eventtype': 'authentication',
                 'host': 'host'} for _ in range(2000)]
        result = self.batcher._send_logs_to_stream_alert('duo_auth', logs)

        assert_false(result)

    @patch('app_integrations.batcher.Batcher._send_logs_to_stream_alert')
    def test_segment_and_send(self, batcher_mock):
        """App Integration Batcher - Segment and Send Logs to StreamAlert"""
        logs = [{'timestamp': 'time',
                 'eventtype': 'authentication',
                 'host': 'host'} for _ in range(3000)]
        self.batcher._segment_and_send('duo_auth', logs)

        assert_equal(batcher_mock.call_count, 2)

    @patch('app_integrations.batcher.Batcher._send_logs_to_stream_alert')
    def test_segment_and_send_multi(self, batcher_mock):
        """App Integration Batcher - Segment and Send Logs to StreamAlert, Multi-segment"""
        batcher_mock.side_effect = [False, True, True, True]
        logs = [{'timestamp': 'time',
                 'eventtype': 'authentication',
                 'host': 'host'} for _ in range(6000)]
        self.batcher._segment_and_send('duo_auth', logs)

        assert_equal(batcher_mock.call_count, 4)

    @patch('app_integrations.batcher.Batcher._segment_and_send')
    def test_send_logs_one_batch(self, batcher_mock):
        """App Integration Batcher - Send Logs, One batch"""
        logs = [{'timestamp': 'time',
                 'eventtype': 'authentication',
                 'host': 'host'} for _ in range(1000)]
        self.batcher.send_logs('duo_auth', logs)

        batcher_mock.assert_not_called()

    @patch('app_integrations.batcher.Batcher._segment_and_send')
    def test_send_logs_multi_batch(self, batcher_mock):
        """App Integration Batcher - Send Logs, Multi-batch"""
        logs = [{'timestamp': 'time',
                 'eventtype': 'authentication',
                 'host': 'host'} for _ in range(3000)]
        self.batcher.send_logs('duo_auth', logs)

        batcher_mock.assert_called()
