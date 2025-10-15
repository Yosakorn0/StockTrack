import socket
import threading
import time
import yfinance as yf

HOST = '127.0.0.1'
PORT = 65432

AUTHORIZED_USERS = ["Yosakorn"]

# Status codes
STATUS_CODES = {
    100: "CONTINUE - Command received and being processed",
    200: "OK",
    400: "BAD_REQUEST - Invalid command",
    401: "UNAUTHORIZED - Invalid username",
    404: "NOT_FOUND - Stock ticker not found",
    500: "SERVER_ERROR - Server-side exception",
    501: "SERVER_SHUTDOWN - Server is stopping",
    2000: "OK (logout) - Successful logout"
}

def get_live_price(symbol):
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period="1d")
        if not data.empty:
            return round(data["Close"].iloc[-1], 2)
        return None
    except Exception:
        return None

def send_status(conn, code, message=""):
    """Send a message with status code and emoji."""
    emoji_map = {
        100: "📈",   # Continue / Stock update
        200: "✅",   # Success
        2000: "🛑",  # Logout
        400: "⚠️",  # Bad request
        401: "❌",  # Unauthorized
        404: "❌",  # Not found
        500: "💥",  # Server error
        501: "💤"   # Server shutdown
    }
    emoji = emoji_map.get(code, "")
    msg = f"{code} {STATUS_CODES.get(code, '')} {emoji}"
    if message:
        msg += f" | {message}"
    conn.sendall(f"{msg}\n".encode())


def handle_client(conn, addr):
    print(f"[CONNECTED] {addr}")
    try:
        # Authenticate user
        conn.sendall(b"Enter your username: ")
        username = conn.recv(1024).decode().strip()
        if username not in AUTHORIZED_USERS:
            send_status(conn, 401)
            conn.close()
            print(f"[DISCONNECTED] Unauthorized user {username}")
            return

        send_status(conn, 200, f"Welcome {username}! Login successful.")
        print(f"[AUTHORIZED] {username} connected from {addr}")

        active = True
        while active:
            menu = (
                "\n===== STOCK MENU =====\n"
                "1. View live stock prices (auto-refresh)\n"
                "2. Subscribe to a stock (continuous updates)\n"
                "3. Exit\n"
                "Enter choice: "
            )
            conn.sendall(menu.encode())
            choice = conn.recv(1024).decode().strip().lower()
            if not choice:
                send_status(conn, 400, "No input received")
                continue

            # Option 1: Auto-refresh multiple stocks
            if choice == "1":
                conn.sendall(b"Enter stock symbols separated by comma (e.g., AAPL,GOOG): ")
                symbols_input = conn.recv(1024).decode().strip().upper()
                symbols = [s.strip() for s in symbols_input.split(",") if s.strip()]
                if not symbols:
                    send_status(conn, 400, "No valid symbols entered")
                    continue

                conn.sendall(b"Displaying live stock prices every 5 seconds. Type 'stop' to return.\n")
                conn.settimeout(5)

                while True:
                    try:
                        prices = []
                        for symbol in symbols:
                            price = get_live_price(symbol)
                            if price is not None:
                                conn.sendall(f"{100} {STATUS_CODES[100]} 📈 | {symbol}: ${price}\n".encode())
                            else:
                                send_status(conn, 404, f"{symbol} not found")
                        conn.sendall(f"{100} {STATUS_CODES[100]} | \n{'\n'.join(prices)}\n".encode())

                        # Check for stop or exit
                        try:
                            data = conn.recv(1024).decode().strip().lower()
                            if data in ["stop", "exit", "quit", "3"]:
                                send_status(conn, 200, "Stopped live monitoring")
                                conn.settimeout(None)
                                break
                        except socket.timeout:
                            continue
                    except Exception as e:
                        send_status(conn, 500, str(e))
                        break

            # Option 2: Subscribe to single stock
            elif choice == "2":
                conn.sendall(b"Enter a stock symbol to subscribe: ")
                symbol = conn.recv(1024).decode().strip().upper()
                if not symbol:
                    send_status(conn, 400, "No symbol entered")
                    continue

                conn.sendall(f"Subscribed to {symbol}. Updating every 5 seconds. Type 'stop' or 'exit' to unsubscribe.\n".encode())
                conn.settimeout(5)
                while True:
                    try:
                        price = get_live_price(symbol)
                        if price is not None:
                            conn.sendall(f"{100} {STATUS_CODES[100]} | {symbol}: ${price}\n".encode())
                        else:
                            send_status(conn, 404, f"{symbol} not found")

                        try:
                            data = conn.recv(1024).decode().strip().lower()
                            if data in ["stop", "exit", "quit", "3"]:
                                send_status(conn, 200, f"Unsubscribed from {symbol}")
                                conn.settimeout(None)
                                break
                        except socket.timeout:
                            continue
                    except Exception as e:
                        send_status(conn, 500, str(e))
                        break

            # Option 3 or exit
            elif choice in ["3", "exit", "quit"]:
                send_status(conn, 2000)
                active = False
                break

            else:
                send_status(conn, 400, "Invalid menu option")

    except Exception as e:
        send_status(conn, 500, str(e))
    finally:
        conn.close()
        print(f"[SESSION CLOSED] {username} from {addr}")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SERVER RUNNING] Listening on {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    start_server()
