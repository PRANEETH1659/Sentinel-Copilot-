# PURPOSE OF THE FILE -- PRODUCER: announces a new security alert onto the queue.
#
# This stands in for whatever will eventually detect real alerts (a log
# monitor, an IDS, a SIEM webhook). For now it just lets us manually drop a
# test alert onto the 'security-alerts' topic to prove the pipeline works
# end-to-end, before anything fancier produces alerts for real.

import json
import sys
import time

from kafka import KafkaProducer

from . import config_ph1 as config


def get_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def send_alert(text: str, source: str = "manual-test"):
    producer = get_producer()
    message = {
        "text": text,
        "source": source,
        "timestamp": time.time(),
    }
    producer.send(config.KAFKA_ALERTS_TOPIC, value=message)
    producer.flush()  # block until Redpanda has confirmed receipt
    print(f"Sent alert to '{config.KAFKA_ALERTS_TOPIC}': {text[:80]}")


if __name__ == "__main__":
    # Usage: python -m app.producer_ph4 "Failed SSH login attempts from 203.0.113.45"
    test_text = " ".join(sys.argv[1:]) or (
        "Failed SSH login attempts detected from IP 203.0.113.45 - "
        "47 attempts in 5 minutes on server prod-web-01."
    )
    send_alert(test_text)
