import json
import unittest

from backend.mqtt import MqttPublisher


class FakeClient:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.messages.append((topic, payload, qos, retain))


class MqttPublisherTest(unittest.TestCase):
    def test_home_assistant_discovery_and_availability(self):
        config = {
            "base_topic": "building/noise/", "discovery_prefix": "homeassistant/",
            "qos": 1, "retain": True,
        }
        publisher = MqttPublisher(config, None)
        client = FakeClient()
        publisher._connected(client, None, {}, 0)

        self.assertTrue(publisher.connected)
        self.assertEqual(client.messages[0], ("building/noise/availability", "online", 1, True))
        configs = [message for message in client.messages if message[0].endswith("/config")]
        self.assertEqual(len(configs), 5)
        payload = json.loads(configs[0][1])
        self.assertEqual(payload["availability_topic"], "building/noise/availability")
        self.assertEqual(payload["device"]["identifiers"], ["noisemeter_pro"])
        self.assertTrue(configs[0][3])

    def test_rejected_connection_is_not_marked_connected(self):
        publisher = MqttPublisher({}, None)
        publisher._connected(FakeClient(), None, {}, 5)
        self.assertFalse(publisher.connected)


if __name__ == "__main__":
    unittest.main()
