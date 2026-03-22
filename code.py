import board
import displayio
import terminalio
import wifi
import socketpool
import os
import time
import mdns
import digitalio
from adafruit_display_text import label
from adafruit_httpserver import Server, Request, Response, POST

# --- 1. UI & Display Setup ---
display = board.DISPLAY
window = displayio.Group()
display.root_group = window

def show_text(line1, line2, color1=0xFFFFFF, color2=0xFFFF00):
    """Updates the display with status or quest info."""
    while len(window) > 0:
        window.pop()
    l1 = label.Label(terminalio.FONT, text=line1, color=color1, scale=1, x=5, y=20)
    l2 = label.Label(terminalio.FONT, text=line2, color=color2, scale=2, x=5, y=50)
    window.append(l1)
    window.append(l2)

# --- 2. Physical Buttons (Paws) Setup ---
# Left Paw: Complete (+2)
btn_complete = digitalio.DigitalInOut(board.D5)
btn_complete.direction = digitalio.Direction.INPUT
btn_complete.pull = digitalio.Pull.UP

# Right Paw: Skip (-0.5)
btn_skip = digitalio.DigitalInOut(board.D6)
btn_skip.direction = digitalio.Direction.INPUT
btn_skip.pull = digitalio.Pull.UP

# --- 3. WiFi Connection Loop ---
ssid = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

print(f"Connecting to: {ssid}")
show_text("WiFi Status:", "Connecting...")

while not wifi.radio.connected:
    try:
        wifi.radio.connect(ssid, password)
    except Exception as e:
        print(f"WiFi Error: {e}. Retrying...")
        show_text("Retrying...", "Keep Hotspot Open", color1=0xFF0000)
        time.sleep(3)

my_ip = str(wifi.radio.ipv4_address)
print(f"Connected! IP: {my_ip}")
show_text("Connected!", f"IP: {my_ip}", color1=0x00FF00)

# --- 4. Web Server & API Setup ---
pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)

# Start mDNS so frontend can use http://cat-companion.local
try:
    server_mdns = mdns.Server(wifi.radio)
    server_mdns.hostname = "cat-companion"
    server_mdns.advertise_service(service_type="_http", protocol="_tcp", port=80)
except Exception:
    pass

@server.route("/add_quest", POST)
def add_quest(request: Request):
    try:
        data = request.json()

        # Exact field names from your dashboard screenshot
        q_name = data.get("Quest", "Unknown")
        q_type = data.get("Reminder type", "None")
        q_time = data.get("Reminder time", "None")
        q_dur  = data.get("Quest duration (minutes)", "0")

        print("-" * 30)
        print(f"Quest: {q_name}")
        print(f"Type: {q_type} | Time: {q_time}")
        print(f"Duration: {q_dur}")
        print("-" * 30)

        # Show on the cat's screen
        show_text("New Quest!", q_name[:12], color1=0x00FFFF)

        return Response(request, "Cat received quest!", content_type="text/plain")
    except Exception as e:
        return Response(request, f"Error: {e}", status=400)

server.start(my_ip)

# --- 5. Main Loop ---
print("Ready. Waiting for quests or paw presses...")

while True:
    server.poll()  # Keep the web server alive

    # Check Left Paw (Complete)
    if not btn_complete.value:
        print(">> Left Paw: Task Completed (+2)")
        show_text("Quest Done!", "Level +2", color1=0x00FF00)
        time.sleep(1) # Visual feedback duration
        show_text("Connected!", f"IP: {my_ip}")
        time.sleep(0.5) # Debounce

    # Check Right Paw (Skip)
    if not btn_skip.value:
        print(">> Right Paw: Task Skipped (-0.5)")
        show_text("Quest Skipped", "Level -0.5", color1=0xFF8800)
        time.sleep(1)
        show_text("Connected!", f"IP: {my_ip}")
        time.sleep(0.5)

    time.sleep(0.01)
