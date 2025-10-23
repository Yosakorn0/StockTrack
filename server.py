import socket
import threading
import time
import yfinance as yf
import feedparser

HOST = '127.0.0.1'
PORT = 65432
AUTHORIZED_USERS = ["Yosakorn"]

def get_live_price(symbol):
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period="1d")
        if not data.empty:
            return round(data["Close"].iloc[-1], 2)
        return None
    except Exception:
        return None

def get_news():
    """Fetch latest global market news from RSS feeds."""
    rss_feeds = [
        "https://www.marketwatch.com/rss/topstories",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    ]
    news_items = []
    for url in rss_feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:  # top 5 from each feed
            title = entry.get("title", "No title")
            link = entry.get("link", "")
            source = entry.get("source", {}).get("title", url)
            news_items.append((title, source, link))
    return news_items[:10]  # return top 10 combined

def get_company_info(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        return {
            "Name": info.get("longName", "N/A"),
            "Sector": info.get("sector", "N/A"),
            "Industry": info.get("industry", "N/A"),
            "Website": info.get("website", "N/A")
        }
    except Exception:
        return None

def get_dividend(symbol):
    try:
        stock = yf.Ticker(symbol)
        div = stock.dividends
        if div.empty:
            return None
        return div.tail(5).to_dict()
    except Exception:
        return None

def send_status(conn, code, message=""):
    STATUS_CODES = {
        100: "📈 CONTINUE - Command received and being processed",
        200: "✅ OK",
        2000: "🛑 OK (logout) - Successful logout",
        400: "⚠️ BAD_REQUEST - Invalid command",
        401: "❌ UNAUTHORIZED - Invalid username",
        404: "❌ NOT_FOUND - Stock ticker not found",
        500: "💥 SERVER_ERROR - Server-side exception",
        501: "💤 SERVER_SHUTDOWN - Server is stopping"
    }
    msg = f"{code} {STATUS_CODES.get(code, '')}"
    if message:
        msg += f" | {message}"
    print(f"[SERVER STATUS] {msg}")  # log on server
    try:
        conn.sendall(f"{msg}\n".encode())  # send to client
    except Exception:
        pass

def handle_client(conn, addr):
    print(f"[CONNECTED] {addr}")
    subscribed = []  # per-client subscription list
    username = "UNKNOWN"
    try:
        # Ask for username
        conn.sendall(b"Enter your username: ")
        username = conn.recv(1024).decode().strip()
        print(f"[DEBUG] Received username: '{username}'")

        # Check authorization
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
                "2. Subscribe to stocks (continuous updates)\n"
                "3. View latest global market news\n"
                "4. View company info\n"
                "5. View dividend info\n"
                "6. Exit\n"
                "Type 'back' in any submenu to return to this menu.\n"
                "Enter choice: "
            )
            conn.sendall(menu.encode())
            choice = conn.recv(1024).decode().strip().lower()
            if not choice:
                send_status(conn, 400, "No input received")
                continue

            # Option 1: Live stock prices
            if choice == "1":
                conn.sendall(b"Enter stock symbols separated by comma (e.g., AAPL,GOOG): ")
                symbols_input = conn.recv(1024).decode().strip().upper()
                symbols = [s.strip() for s in symbols_input.split(",") if s.strip()]
                if not symbols:
                    send_status(conn, 400, "No valid symbols entered")
                    continue

                conn.sendall(b"Displaying live stock prices every 5 seconds. Type 'stop' or 'back' to return.\n")
                conn.settimeout(5)
                while True:
                    try:
                        for symbol in symbols:
                            price = get_live_price(symbol)
                            if price is not None:
                                conn.sendall(f"📊 {symbol}: ${price}\n".encode())
                            else:
                                send_status(conn, 404, f"{symbol} not found")

                        try:
                            data = conn.recv(1024).decode().strip().lower()
                            if data in ["stop", "exit", "quit"]:
                                send_status(conn, 200, "Stopped live monitoring")
                                conn.settimeout(None)
                                break
                            elif data == "back":
                                send_status(conn, 200, "Returning to main menu")
                                conn.settimeout(None)
                                break
                        except socket.timeout:
                            continue
                    except Exception as e:
                        send_status(conn, 500, str(e))
                        break

            # Option 2: Subscribe to multiple stocks (subscription list)
            elif choice == "2":
                while True:
                    conn.sendall(
                        b"\nEnter a stock symbol to subscribe, 'remove' to remove a stock, or 'done' to start updates: "
                    )
                    symbol = conn.recv(1024).decode().strip().upper()

                    if symbol.lower() == "done":
                        if not subscribed:
                            send_status(conn, 400, "No stocks subscribed yet")
                            continue
                        break
                    elif symbol.lower() == "remove":
                        # Show current subscriptions
                        if not subscribed:
                            send_status(conn, 400, "No stocks to remove")
                            continue
                        conn.sendall(f"Current subscriptions: {', '.join(subscribed)}\n".encode())
                        conn.sendall(b"Enter a stock symbol to remove: ")
                        remove_symbol = conn.recv(1024).decode().strip().upper()
                        if remove_symbol in subscribed:
                            subscribed.remove(remove_symbol)
                            send_status(conn, 200, f"Removed {remove_symbol} from subscriptions")
                        else:
                            send_status(conn, 404, f"{remove_symbol} is not in your subscriptions")
                        continue
                    elif not symbol:
                        send_status(conn, 400, "No symbol entered")
                        continue
                    else:
                        if symbol not in subscribed:
                            subscribed.append(symbol)
                            send_status(conn, 200, f"Subscribed to {symbol}")
                        else:
                            send_status(conn, 200, f"{symbol} already in subscription list")

                # Start live updates
                conn.sendall(
                    f"Updating subscribed stocks every 5 seconds: {', '.join(subscribed)}. Type 'stop', 'back', or 'exit' to return.\n".encode()
                )
                conn.settimeout(5)

                while True:
                    try:
                        for symbol in subscribed:
                            price = get_live_price(symbol)
                            if price is not None:
                                conn.sendall(f"📊 {symbol}: ${price}\n".encode())
                            else:
                                send_status(conn, 404, f"{symbol} not found")

                        try:
                            data = conn.recv(1024).decode().strip().lower()
                            if data in ["stop", "exit", "quit"]:
                                send_status(conn, 200, "Stopped subscription")
                                conn.settimeout(None)
                                break
                            elif data == "back":
                                send_status(conn, 200, "Returning to main menu")
                                conn.settimeout(None)
                                break
                        except socket.timeout:
                            continue
                    except Exception as e:
                        send_status(conn, 500, str(e))
                        break


            # Option 3: Global market news
            elif choice == "3":
                conn.sendall("\n📰 Fetching latest global market news...\n".encode())
                news_items = get_news()
                if not news_items:
                    send_status(conn, 404, "No market news found")
                    continue

                for i, (title, publisher, link) in enumerate(news_items, start=1):
                    conn.sendall(f"{i}. {title} — {publisher}\n🔗 {link}\n\n".encode())
                conn.sendall("Type 'back' to return to the main menu.\n".encode())
                try:
                    data = conn.recv(1024).decode().strip().lower()
                    if data == "back":
                        send_status(conn, 200, "Returning to main menu")
                        continue
                except socket.timeout:
                    pass
                send_status(conn, 200, f"Displayed top {len(news_items)} market news articles")

            # Option 4: Company info
            elif choice == "4":
                conn.sendall(b"Enter a stock symbol to view company info: ")
                symbol = conn.recv(1024).decode().strip().upper()
                info = get_company_info(symbol)
                if not info:
                    send_status(conn, 404, f"No company info found for {symbol}")
                    continue
                for key, value in info.items():
                    conn.sendall(f"{key}: {value}\n".encode())
                conn.sendall("Type 'back' to return to the main menu.\n".encode())
                try:
                    data = conn.recv(1024).decode().strip().lower()
                    if data == "back":
                        send_status(conn, 200, "Returning to main menu")
                        continue
                except socket.timeout:
                    pass
                send_status(conn, 200, f"Displayed company info for {symbol}")

            # Option 5: Dividend info
            elif choice == "5":
                conn.sendall(b"Enter a stock symbol to view dividend info: ")
                symbol = conn.recv(1024).decode().strip().upper()
                dividends = get_dividend(symbol)
                if not dividends:
                    send_status(conn, 404, f"No dividend data found for {symbol}")
                    continue

                conn.sendall("Date | Dividend\n".encode())
                conn.sendall(("-" * 30 + "\n").encode())
                for date, value in dividends.items():
                    # Ensure date is string
                    if hasattr(date, "date"):
                        date_str = str(date.date())
                    else:
                        date_str = str(date)
                    # Ensure value is float
                    try:
                        value_float = float(value)
                    except Exception:
                        value_float = 0.0
                    conn.sendall(f"{date_str} | ${value_float:.2f}\n".encode())

                conn.sendall("Type 'back' to return to the main menu.\n".encode())

                try:
                    data = conn.recv(1024).decode().strip().lower()
                    if data == "back":
                        send_status(conn, 200, "Returning to main menu")
                        continue
                except socket.timeout:
                    pass
                send_status(conn, 200, f"Displayed dividend info for {symbol}")

            # Option 6: Exit
            elif choice in ["6", "exit", "quit"]:
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
