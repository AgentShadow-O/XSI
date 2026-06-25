from __future__ import annotations

from typing import Any, Callable

from backend.sensors.ids.parsers import ids_alert_to_event


class NetworkSensor:
    """Adapter for the legacy Scapy IDS packet rules."""

    def packet_to_event(self, packet: Any) -> list:
        events = []
        try:
            from scapy.layers.inet import IP, TCP
        except ImportError:
            return events

        if IP not in packet:
            return events
        ip_src = packet[IP].src
        if TCP in packet:
            flags = packet[TCP].flags
            dport = int(packet[TCP].dport)
            if flags == "S":
                events.append(
                    ids_alert_to_event(
                        {
                            "event_type": "SYN_FLOOD",
                            "severity": "critical",
                            "risk_score": 80,
                            "ip": ip_src,
                            "protocol": "tcp",
                            "port": dport,
                            "message": "Possible SYN flood detected",
                        }
                    )
                )
            if dport < 1024:
                events.append(
                    ids_alert_to_event(
                        {
                            "event_type": "PORT_SCAN",
                            "severity": "warning",
                            "risk_score": 60,
                            "ip": ip_src,
                            "protocol": "tcp",
                            "port": dport,
                            "message": "Port scan behavior detected",
                        }
                    )
                )
        return events

    def start(self, publish: Callable[[Any], None]) -> None:
        try:
            from scapy.all import sniff
        except ImportError:
            return

        def _handle(packet: Any) -> None:
            for event in self.packet_to_event(packet):
                publish(event)

        sniff(prn=_handle, store=0)
