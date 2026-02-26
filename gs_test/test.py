# p2p_blockchain.py - 간단한 P2P 블록체인
# 사용법: python test.py <내포트> [상대IP:포트]
# 예시:
#   터미널1: python test.py 8001
#   터미널2: python test.py 8002 127.0.0.1:8001
#
# 명령어:
#   mine <데이터>  - 블록 채굴
#   chain         - 체인 보기
#   sync          - 피어와 체인 동기화
#   quit          - 종료

import socket
import threading
import sys
import json
import time
import os

from consensus import Consensus

# ========== 저장소 ==========

DATA_DIR = "chain_data"

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_chain_file(port):
    return os.path.join(DATA_DIR, f"chain_{port}.json")

# ========== 블록체인 ==========

class Block:
    def __init__(self, index, prev_hash, data, timestamp=None, nonce=0, hash=None):
        self.index = index
        self.prev_hash = prev_hash
        self.data = data
        self.timestamp = time.time() if timestamp is None else timestamp
        self.nonce = nonce
        self.hash = hash or Consensus.calculate_hash(index, prev_hash, data, self.timestamp, nonce)

    def mine(self):
        """PoW 채굴 (consensus 모듈 사용)"""
        return Consensus.mine(self)

    def to_dict(self):
        return {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "data": self.data,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d["index"], d["prev_hash"], d["data"], d["timestamp"], d["nonce"], d["hash"])

    def __str__(self):
        return f"Block#{self.index} [{self.hash[:8]}...] data='{self.data}'"


class Blockchain:
    def __init__(self, port=None):
        self.port = port
        self.chain = self.load() or [self.create_genesis()]

    def create_genesis(self):
        return Block(0, "0" * 64, "Genesis Block", 0, 0).mine()

    def get_latest(self):
        return self.chain[-1]

    def add_block(self, block):
        """블록 추가 + 검증"""
        if block.index != len(self.chain):
            return False
        if block.prev_hash != self.get_latest().hash:
            return False
        if not Consensus.is_valid_block(block, self.get_latest()):
            return False
        self.chain.append(block)
        self.save()
        return True

    def mine_block(self, data):
        """새 블록 채굴"""
        prev = self.get_latest()
        new_block = Block(prev.index + 1, prev.hash, data)
        new_block.mine()
        self.chain.append(new_block)
        self.save()
        return new_block

    def replace_chain(self, new_chain):
        """더 긴 체인으로 교체 (Longest Chain Rule)"""
        replaced, result = Consensus.resolve_conflicts(self.chain, new_chain)
        if replaced:
            self.chain = result
            self.save()
            return True
        return False

    # ===== 저장/로드 =====
    def save(self):
        """체인을 JSON 파일로 저장"""
        if not self.port:
            return
        ensure_data_dir()
        filepath = get_chain_file(self.port)
        data = [b.to_dict() for b in self.chain]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load(self):
        """JSON 파일에서 체인 로드"""
        if not self.port:
            return None
        filepath = get_chain_file(self.port)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            chain = [Block.from_dict(b) for b in data]
            if Consensus.is_valid_chain(chain):
                print(f"[로드] {filepath}에서 {len(chain)}개 블록 로드됨")
                return chain
        except Exception as e:
            print(f"[로드 실패] {e}")
        return None

    def print_chain(self):
        print("\n===== 블록체인 =====")
        for b in self.chain:
            print(f"  #{b.index} | {b.hash[:16]}... | {b.data}")
        print(f"총 {len(self.chain)}개 블록")
        print("===================\n")

# ========== P2P 노드 ==========

class P2PNode:
    def __init__(self, port):
        self.port = port
        self.peers = []  # 연결된 피어 소켓들
        self.running = True
        self.blockchain = Blockchain(port)  # 각 노드가 체인 보유 (포트별 저장)

    def start_server(self):
        """다른 노드의 연결을 받는 서버"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', self.port))
        server.listen(5)
        print(f"[서버] 포트 {self.port}에서 대기 중...")

        while self.running:
            try:
                server.settimeout(1.0)
                conn, addr = server.accept()
                print(f"[연결] {addr}에서 연결됨")
                self.peers.append(conn)
                # 이 피어의 메시지를 처리할 스레드 시작
                threading.Thread(target=self.handle_peer, args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[에러] {e}")

    def connect_to_peer(self, host, port):
        """다른 노드에 연결하는 클라이언트"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            print(f"[연결 성공] {host}:{port}")
            self.peers.append(sock)
            # 이 피어의 메시지를 처리할 스레드 시작
            threading.Thread(target=self.handle_peer, args=(sock, (host, port)), daemon=True).start()
            return True
        except Exception as e:
            print(f"[연결 실패] {host}:{port} - {e}")
            return False

    def handle_peer(self, conn, addr):
        """피어로부터 메시지 수신"""
        while self.running:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                msg = data.decode('utf-8')

                # 메시지 타입별 처리
                if msg.startswith("BLOCK:"):
                    block_json = msg[6:]
                    block_data = json.loads(block_json)
                    block = Block.from_dict(block_data)
                    if self.blockchain.add_block(block):
                        print(f"\n[블록 수신] {block}")
                    else:
                        print(f"\n[블록 거부] {block} (이미 있거나 순서 안맞음)")
                    print("명령어: ", end='', flush=True)

                elif msg.startswith("GETCHAIN"):
                    # 체인 요청 → 내 체인 전송
                    self.send_chain(conn)

                elif msg.startswith("CHAIN:"):
                    # 체인 수신 → 더 길면 교체
                    chain_json = msg[6:]
                    chain_data = json.loads(chain_json)
                    new_chain = [Block.from_dict(b) for b in chain_data]
                    if self.blockchain.replace_chain(new_chain):
                        print(f"\n[동기화] 체인 교체됨! (길이: {len(new_chain)})")
                    else:
                        print(f"\n[동기화] 내 체인 유지 (상대: {len(new_chain)}, 나: {len(self.blockchain.chain)})")
                    print("명령어: ", end='', flush=True)

                else:
                    print(f"\n[{addr}] {msg}")
                    print("명령어: ", end='', flush=True)
            except:
                break
        print(f"[연결 종료] {addr}")
        if conn in self.peers:
            self.peers.remove(conn)
        conn.close()

    def broadcast(self, message):
        """모든 피어에게 메시지 전송"""
        for peer in self.peers[:]:  # 복사본으로 순회
            try:
                peer.send(message.encode('utf-8'))
            except:
                self.peers.remove(peer)

    def broadcast_block(self, block):
        """블록을 모든 피어에게 전파"""
        block_msg = "BLOCK:" + json.dumps(block.to_dict())
        self.broadcast(block_msg)

    def send_chain(self, conn):
        """특정 피어에게 내 체인 전송"""
        chain_data = [b.to_dict() for b in self.blockchain.chain]
        chain_msg = "CHAIN:" + json.dumps(chain_data)
        try:
            conn.send(chain_msg.encode('utf-8'))
        except:
            pass

    def request_sync(self):
        """모든 피어에게 체인 요청"""
        self.broadcast("GETCHAIN")

    def run(self):
        """노드 실행"""
        # 서버 스레드 시작
        threading.Thread(target=self.start_server, daemon=True).start()

        print("\n명령어:")
        print("  mine <데이터>  - 블록 채굴")
        print("  chain         - 체인 보기")
        print("  sync          - 피어와 동기화")
        print("  quit          - 종료")
        print("-" * 40)

        while True:
            try:
                cmd = input("명령어: ").strip()
                if not cmd:
                    continue

                if cmd.lower() == 'quit':
                    break

                elif cmd.lower() == 'chain':
                    self.blockchain.print_chain()

                elif cmd.lower() == 'sync':
                    print(f"[동기화] {len(self.peers)}개 피어에게 체인 요청...")
                    self.request_sync()

                elif cmd.lower().startswith('mine '):
                    data = cmd[5:]
                    print(f"[채굴중] '{data}'...")
                    block = self.blockchain.mine_block(data)
                    print(f"[채굴완료] {block}")
                    self.broadcast_block(block)
                    print(f"[전파] {len(self.peers)}개 피어에게 전송")

                else:
                    # 일반 메시지
                    self.broadcast(f"[노드:{self.port}] {cmd}")
                    print(f"[전송] {len(self.peers)}개 피어에게 전송됨")

            except KeyboardInterrupt:
                break

        self.running = False
        print("\n종료 중...")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python test.py <포트> [상대IP:포트]")
        print("예시:")
        print("  터미널1: python test.py 8001")
        print("  터미널2: python test.py 8002 127.0.0.1:8001")
        sys.exit(1)

    my_port = int(sys.argv[1])
    node = P2PNode(my_port)

    # 연결할 피어가 있으면 연결
    if len(sys.argv) >= 3:
        peer_addr = sys.argv[2]
        host, port = peer_addr.split(':')
        node.connect_to_peer(host, int(port))

    node.run()