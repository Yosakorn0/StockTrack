import socket
import threading
import sys

HOST = '127.0.0.1'
PORT = 65432

def receive_messages(sock):
    while True:
        try:
            data = sock.recv(1024).decode()
            if not data:
                print("\n[SERVER CLOSED CONNECTION]")
                break
            # Print status code messages clearly
            print(data, end='')
        except (ConnectionResetError, OSError):
            print("\n[CONNECTION TERMINATED]")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")
            break

def start_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
            print(f"[CONNECTED] Connected to {HOST}:{PORT}")
        except ConnectionRefusedError:
            print("Server not available.")
            return

        listener = threading.Thread(target=receive_messages, args=(s,), daemon=True)
        listener.start()

        while True:
            try:
                user_input = input()
                if not user_input:
                    continue
                s.sendall(user_input.encode())

                if user_input.strip().lower() in ["3", "exit", "quit"]:
                    print("[DISCONNECTED] Session terminated.")
                    s.close()
                    sys.exit()
            except (KeyboardInterrupt, EOFError):
                print("\n[CLIENT EXITED]")
                s.close()
                break

if __name__ == "__main__":
    start_client()
