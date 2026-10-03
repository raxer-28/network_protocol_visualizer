"""
TCP Simulator — Generates detailed Transport-layer ProtocolSteps for TCP.
"""
from backend.models import ProtocolStep, HighlightField
import time

def generate_tcp_handshake(t0_ms: float, client_ip: str, server_ip: str, port: int, step_offset: int, seq_start: int = 0) -> list[ProtocolStep]:
    steps = []
    # 1. SYN
    steps.append(ProtocolStep(
        id=step_offset + 1,
        phase="TCP",
        direction="client→server",
        label=f"SYN (Seq={seq_start})",
        detail=f"TCP Segment\nFlags: [SYN]\nSeq: {seq_start}\nWin: 64240\nLength: 0",
        highlight_fields=[
            HighlightField(key="Flags", value="SYN"),
            HighlightField(key="Seq", value=str(seq_start)),
            HighlightField(key="Win", value="64240"),
            HighlightField(key="Length", value="0")
        ],
        timestamp_ms=t0_ms,
        layer="transport"
    ))
    # 2. SYN-ACK
    steps.append(ProtocolStep(
        id=step_offset + 2,
        phase="TCP",
        direction="server→client",
        label=f"SYN-ACK (Seq=0, Ack={seq_start+1})",
        detail=f"TCP Segment\nFlags: [SYN, ACK]\nSeq: 0\nAck: {seq_start+1}\nWin: 65535\nLength: 0",
        highlight_fields=[
            HighlightField(key="Flags", value="SYN, ACK"),
            HighlightField(key="Seq", value="0"),
            HighlightField(key="Ack", value=str(seq_start+1)),
            HighlightField(key="Win", value="65535")
        ],
        timestamp_ms=t0_ms + 15,
        layer="transport"
    ))
    # 3. ACK
    steps.append(ProtocolStep(
        id=step_offset + 3,
        phase="TCP",
        direction="client→server",
        label=f"ACK (Seq={seq_start+1}, Ack=1)",
        detail=f"TCP Segment\nFlags: [ACK]\nSeq: {seq_start+1}\nAck: 1\nWin: 64240\nLength: 0",
        highlight_fields=[
            HighlightField(key="Flags", value="ACK"),
            HighlightField(key="Seq", value=str(seq_start+1)),
            HighlightField(key="Ack", value="1"),
            HighlightField(key="Win", value="64240")
        ],
        timestamp_ms=t0_ms + 30,
        layer="transport"
    ))
    return steps

def generate_tcp_data(t0_ms: float, direction: str, seq: int, ack: int, length: int, flags: str = "PSH, ACK", step_offset: int = 0) -> list[ProtocolStep]:
    # Single data segment and its ACK
    steps = []
    
    steps.append(ProtocolStep(
        id=step_offset + 1,
        phase="TCP",
        direction=direction,
        label=f"{flags} (Seq={seq}, Len={length})",
        detail=f"TCP Segment\nFlags: [{flags}]\nSeq: {seq}\nAck: {ack}\nWin: 64240\nLength: {length}",
        highlight_fields=[
            HighlightField(key="Flags", value=flags),
            HighlightField(key="Seq", value=str(seq)),
            HighlightField(key="Ack", value=str(ack)),
            HighlightField(key="Win", value="64240"),
            HighlightField(key="Length", value=str(length))
        ],
        timestamp_ms=t0_ms,
        layer="transport"
    ))
    
    # ACK from the other side
    rev_direction = "server→client" if direction == "client→server" else "client→server"
    steps.append(ProtocolStep(
        id=step_offset + 2,
        phase="TCP",
        direction=rev_direction,
        label=f"ACK (Ack={seq + length})",
        detail=f"TCP Segment\nFlags: [ACK]\nSeq: {ack}\nAck: {seq + length}\nLength: 0",
        highlight_fields=[
            HighlightField(key="Flags", value="ACK"),
            HighlightField(key="Seq", value=str(ack)),
            HighlightField(key="Ack", value=str(seq + length))
        ],
        timestamp_ms=t0_ms + 20,
        layer="transport"
    ))
    return steps

def generate_tcp_teardown(t0_ms: float, client_seq: int, server_seq: int, step_offset: int = 0) -> list[ProtocolStep]:
    steps = []
    # 1. FIN-ACK (Client)
    steps.append(ProtocolStep(
        id=step_offset + 1,
        phase="TCP",
        direction="client→server",
        label=f"FIN-ACK (Seq={client_seq})",
        detail=f"TCP Segment\nFlags: [FIN, ACK]\nSeq: {client_seq}\nAck: {server_seq}\nLength: 0",
        highlight_fields=[
            HighlightField(key="Flags", value="FIN, ACK"),
            HighlightField(key="Seq", value=str(client_seq))
        ],
        timestamp_ms=t0_ms,
        layer="transport"
    ))
    # 2. ACK (Server)
    steps.append(ProtocolStep(
        id=step_offset + 2,
        phase="TCP",
        direction="server→client",
        label=f"ACK (Ack={client_seq+1})",
        detail=f"TCP Segment\nFlags: [ACK]\nSeq: {server_seq}\nAck: {client_seq+1}\nLength: 0",
        highlight_fields=[
            HighlightField(key="Flags", value="ACK"),
            HighlightField(key="Ack", value=str(client_seq+1))
        ],
        timestamp_ms=t0_ms + 15,
        layer="transport"
    ))
    # 3. FIN-ACK (Server)
    steps.append(ProtocolStep(
        id=step_offset + 3,
        phase="TCP",
        direction="server→client",
        label=f"FIN-ACK (Seq={server_seq})",
        detail=f"TCP Segment\nFlags: [FIN, ACK]\nSeq: {server_seq}\nAck: {client_seq+1}\nLength: 0",
        highlight_fields=[
            HighlightField(key="Flags", value="FIN, ACK"),
            HighlightField(key="Seq", value=str(server_seq))
        ],
        timestamp_ms=t0_ms + 30,
        layer="transport"
    ))
    # 4. ACK (Client)
    steps.append(ProtocolStep(
        id=step_offset + 4,
        phase="TCP",
        direction="client→server",
        label=f"ACK (Ack={server_seq+1})",
        detail=f"TCP Segment\nFlags: [ACK]\nSeq: {client_seq+1}\nAck: {server_seq+1}\nLength: 0",
        highlight_fields=[
            HighlightField(key="Flags", value="ACK"),
            HighlightField(key="Ack", value=str(server_seq+1))
        ],
        timestamp_ms=t0_ms + 45,
        layer="transport"
    ))
    return steps

def generate_udp_datagrams(t0_ms: float, direction: str, src_port: int, dst_port: int, total_bytes: int, step_offset: int = 0) -> list[ProtocolStep]:
    steps = []
    chunk_size = 1400  # Typical UDP MTU payload
    num_packets = (total_bytes + chunk_size - 1) // chunk_size

    detail = (
        f"[UDP Burst Transfer]\n"
        f"Src Port: {src_port}  ->  Dst Port: {dst_port}\n"
        f"Total Packets: {num_packets}\n"
        f"Total Length: {total_bytes} bytes\n"
        f"Checksum: 0xABCD (valid)\n\n"
        f"[Payload: {total_bytes} bytes of binary data]"
    )
    
    steps.append(ProtocolStep(
        id=step_offset + 1,
        phase="UDP",
        direction=direction,
        label=f"UDP Burst ({num_packets} datagrams)",
        detail=detail,
        highlight_fields=[
            HighlightField(key="Src Port", value=str(src_port)),
            HighlightField(key="Dst Port", value=str(dst_port)),
            HighlightField(key="Packets", value=str(num_packets)),
            HighlightField(key="Total Size", value=f"{total_bytes} bytes")
        ],
        timestamp_ms=t0_ms,
        layer="transport"
    ))
    
    return steps
