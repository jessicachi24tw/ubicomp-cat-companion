import board
import displayio
import terminalio
import wifi
import socketpool
import adafruit_requests
import time
import digitalio
from adafruit_display_text import label
from adafruit_httpserver import Server, Request, Response, POST

# --- 1. WiFi Connection (RedRover Campus Mode) ---
print("Connecting to RedRover...")
try:
    wifi.radio.connect("RedRover")
    print("Connected to RedRover!")
except Exception:
    print("RedRover network was not found!")
    print("Are you on campus right now?")
    while True:
        pass

# --- 2. Initialize Display ---
display = board.DISPLAY
window = displayio.Group()
display.root_group = window

def show_text(line1, line2, color1=0xFFFFFF, color2=0xFFFF00):
    """Updates the display with current state and quest title."""
    while len(window) > 0:
        window.pop()
    l1 = label.Label(terminalio.FONT, text=line1, color=color1, scale=1, x=5, y=15)
    l2 = label.Label(terminalio.FONT, text=line2, color=color2, scale=2, x=5, y=45)
    window.append(l1)
    window.append(l2)

my_ip = str(wifi.radio.ipv4_address)
show_text("Connected!", f"IP: {my_ip}", color1=0x00FF00)

# --- 3. Hardware Pins ---
# Left Paw (Complete)
btn_complete = digitalio.DigitalInOut(board.D5)
btn_complete.direction = digitalio.Direction.INPUT
btn_complete.pull = digitalio.Pull.UP

# Right Paw (Skip)
btn_skip = digitalio.DigitalInOut(board.D6)
btn_skip.direction = digitalio.Direction.INPUT
btn_skip.pull = digitalio.Pull.UP

# --- 4. Global State Tracking ---
current_quest_id = None
quest_start_time = 0
auto_skip_duration = 0
cat_state = "idle"

# --- 5. Web Server Setup ---
pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)

def send_event_to_console(event_type):
    """Prints the specific JSON format required by the frontend."""
    event_output = {
        "event_type": event_type,
        "quest_id": current_quest_id,
        "timestamp": f"{time.monotonic():.2f}s",
        "source": "gesture"
    }
    print("\n>>> EVENT FOR FRONTEND:")
    print(event_output)
    print(">>> END EVENT\n")

@server.route("/add_quest", POST)
def add_quest(request: Request):
    global current_quest_id, quest_start_time, auto_skip_duration, cat_state
    try:
        data = request.json()

        # New JSON Structure Mapping
        cat_state = data.get("state", "idle")
        active_quest = data.get("active_quest", {})

        current_quest_id = active_quest.get("id")
        title = active_quest.get("title", "No Title")
        duration_mins = active_quest.get("duration_minutes", 0)

        # Auto-skip logic: (Duration + 10 minutes grace) converted to seconds
        auto_skip_duration = (duration_mins + 10) * 60
        quest_start_time = time.monotonic()

        print(f"--- New State: {cat_state} ---")
        if current_quest_id:
            print(f"Quest Active: {title} (ID: {current_quest_id})")
            show_text(f"State: {cat_state}", title[:12], color1=0x00FFFF)
        else:
            show_text("State:", cat_state, color1=0xAAAAAA)

        return Response(request, "State Updated", content_type="text/plain")
    except Exception as e:
        return Response(request, f"Error: {e}", status=400)

server.start(my_ip)

# --- 6. Main Loop ---
print("Waiting for quests...")

while True:
    server.poll()
    now = time.monotonic()

    # Only check interaction/timers if a quest is active
    if current_quest_id is not None:

        # A. Manual Completion (Left Paw)
        if not btn_complete.value:
            send_event_to_console("quest_completed")
            show_text("Quest Done!", "+2 Bond", color1=0x00FF00)
            current_quest_id = None
            time.sleep(1.5)
            show_text("Connected!", f"IP: {my_ip}")

        # B. Manual Skip (Right Paw)
        elif not btn_skip.value:
            send_event_to_console("quest_skipped")
            show_text("Skipped", "-0.5 Bond", color1=0xFF8800)
            current_quest_id = None
            time.sleep(1.5)
            show_text("Connected!", f"IP: {my_ip}")

        # C. Automatic Skip (Grace Period Expired)
        elif (now - quest_start_time) > auto_skip_duration:
            print(">> [AUTO-SKIP] No user response.")
            send_event_to_console("quest_skipped")
            show_text("Timed Out", "Auto-Skipped", color1=0xFF0000)
            current_quest_id = None
            time.sleep(1.5)
            show_text("Connected!", f"IP: {my_ip}")

    time.sleep(0.01)
