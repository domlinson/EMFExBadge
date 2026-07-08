from app import App
from app_components import clear_background
from system.eventbus import eventbus
from events.input import ButtonDownEvent, BUTTON_TYPES

class EMFExTracker(App):
    def __init__(self):
        # Register the button event listener
        eventbus.on(ButtonDownEvent, self._handle_buttondown, self)
        
        # Initialize application state
        self.state = "SPLASH"
        self.splash_timer = 0
        
        # Track active digit edit state (6 digits)
        self.digits = [0, 0, 0, 0, 0, 0]
        self.active_digit_index = 0
        
        # Asset and JSON paths resolution
        try:
            if '/' in __file__:
                dir_path = __file__.rsplit('/', 1)[0]
            else:
                dir_path = "."
            self.logo_path = dir_path + "/logo.png"
            self.recents_path = dir_path + "/recents.json"
        except Exception:
            self.logo_path = "logo.png"
            self.recents_path = "recents.json"
            
        self.recents = self._load_recents()
        self.recents_selected_index = 0
        self.job_data = None
        self.error_msg = None

    def _handle_buttondown(self, event: ButtonDownEvent):
        # Exit the app if Button F (CANCEL) is pressed
        if BUTTON_TYPES["CANCEL"] in event.button:
            self.minimise()
            return

        # Ignore other button presses in screens where interaction is not allowed
        if self.state in ["SPLASH", "LOADING_DRAW", "LOADING_FETCH"]:
            return

        if self.state == "INPUT":
            if BUTTON_TYPES["UP"] in event.button:
                # Increment the active digit (0-9)
                self.digits[self.active_digit_index] = (self.digits[self.active_digit_index] + 1) % 10
            elif BUTTON_TYPES["DOWN"] in event.button:
                # Decrement the active digit (0-9)
                self.digits[self.active_digit_index] = (self.digits[self.active_digit_index] - 1) % 10
            elif BUTTON_TYPES["CONFIRM"] in event.button:
                # Confirm button (C)
                if self.active_digit_index < 5:
                    # Move to the next digit
                    self.active_digit_index += 1
                else:
                    # Final number entered, transition to loading flow
                    self.state = "LOADING_DRAW"
            elif BUTTON_TYPES["LEFT"] in event.button:  # Button E
                # Back button (E)
                if self.active_digit_index > 0:
                    # Move back to the previous digit
                    self.active_digit_index -= 1
            elif BUTTON_TYPES["RIGHT"] in event.button:  # Button B
                # Toggle to RECENTS screen
                self.recents_selected_index = 0
                self.state = "RECENTS"

        elif self.state == "RECENTS":
            if BUTTON_TYPES["RIGHT"] in event.button:  # Button B
                # Toggle back to INPUT screen
                self.state = "INPUT"
            elif BUTTON_TYPES["UP"] in event.button:  # Button A
                if len(self.recents) > 0:
                    self.recents_selected_index = (self.recents_selected_index - 1) % len(self.recents)
            elif BUTTON_TYPES["DOWN"] in event.button:  # Button D
                if len(self.recents) > 0:
                    self.recents_selected_index = (self.recents_selected_index + 1) % len(self.recents)
            elif BUTTON_TYPES["CONFIRM"] in event.button:  # Button C
                if len(self.recents) > 0:
                    # Select the tracking number from recents
                    selected_num = self.recents[self.recents_selected_index]
                    self.digits = [int(char) for char in selected_num]
                    self.state = "LOADING_DRAW"

        elif self.state in ["RESULT", "ERROR"]:
            if BUTTON_TYPES["CONFIRM"] in event.button:
                # C button takes them back to the input screen
                self.active_digit_index = 0
                self.state = "INPUT"
            elif BUTTON_TYPES["DOWN"] in event.button:
                # D button triggers a refresh of the API data
                self.state = "LOADING_DRAW"

    def update(self, delta):
        if self.state == "SPLASH":
            self.splash_timer += delta
            if self.splash_timer >= 1000:
                self.state = "INPUT"
        elif self.state == "LOADING_DRAW":
            # Allow one draw frame to display "Loading..." before blocking on urequests
            self.state = "LOADING_FETCH"
        elif self.state == "LOADING_FETCH":
            self._fetch_tracking_info()

    def _fetch_tracking_info(self):
        tracking_num = "".join(str(d) for d in self.digits)
        url = "https://emfex.uk/api/jobs/EMF-{}".format(tracking_num)
        print("[EMFEx] Starting request to URL: {}".format(url))
        
        # Check Wi-Fi status dynamically
        try:
            import network
            wlan = network.WLAN(network.STA_IF)
            print("[EMFEx] WLAN active: {}, connected: {}".format(wlan.active(), wlan.isconnected()))
            if not wlan.isconnected():
                print("[EMFEx] Error: WLAN is not connected!")
                self.error_msg = "WiFi disconnected!"
                self.state = "ERROR"
                return
        except Exception as e:
            print("[EMFEx] Warning: Failed to query network module: {}".format(e))
            # Fallback for simulators or environments where network module is stubbed
            pass
            
        try:
            import requests
            print("[EMFEx] Sending GET request...")
            response = requests.get(url)
            status_code = response.status_code
            print("[EMFEx] Response status code: {}".format(status_code))
            if status_code == 200:
                self.job_data = response.json()
                print("[EMFEx] Successfully retrieved and parsed job JSON!")
                self.state = "RESULT"
                self._add_to_recents(tracking_num)
            elif status_code == 404:
                print("[EMFEx] Error: Job not found (404)")
                self.error_msg = "Job Not Found"
                self.state = "ERROR"
            else:
                print("[EMFEx] Error: Unexpected status code {}".format(status_code))
                self.error_msg = "HTTP Error: {}".format(status_code)
                self.state = "ERROR"
            response.close()
        except Exception as e:
            print("[EMFEx] Exception during request: {}".format(e))
            try:
                import sys
                if hasattr(sys, 'print_exception'):
                    sys.print_exception(e)
            except Exception:
                pass
            self.error_msg = "Network Request Failed"
            self.state = "ERROR"

    def _load_recents(self):
        try:
            import json
            with open(self.recents_path, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [str(item) for item in data if len(str(item)) == 6 and str(item).isdigit()][:5]
        except Exception as e:
            print("[EMFEx] Failed to load recents: {}".format(e))
        return []

    def _save_recents(self):
        try:
            import json
            with open(self.recents_path, "w") as f:
                json.dump(self.recents, f)
            print("[EMFEx] Successfully saved recents: {}".format(self.recents))
        except Exception as e:
            print("[EMFEx] Failed to save recents: {}".format(e))

    def _add_to_recents(self, tracking_num):
        if tracking_num in self.recents:
            self.recents.remove(tracking_num)
        self.recents.insert(0, tracking_num)
        self.recents = self.recents[:5]
        self._save_recents()

    def _truncate(self, text, max_len=22):
        if not text:
            return "N/A"
        if len(text) > max_len:
            return text[:max_len-3] + "..."
        return text

    def draw_splash(self, ctx):
        clear_background(ctx)
        try:
            ctx.image(self.logo_path, -120, -120, 240, 240)
        except Exception:
            # Fallback splash layout if PNG loading fails
            ctx.gray(0.1).rectangle(-120, -120, 240, 240).fill()
            ctx.text_align = ctx.CENTER
            ctx.text_baseline = ctx.MIDDLE
            ctx.font = "Arimo Bold"
            ctx.font_size = 24
            ctx.rgb(1, 1, 1).move_to(0, -20).text("EMFEx")
            ctx.font_size = 18
            ctx.rgb(0.8, 0.8, 0.8).move_to(0, 20).text("Badge Tracker")

    def draw_input(self, ctx):
        clear_background(ctx)
        ctx.save()
        
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        
        # Title
        ctx.font = "Arimo Bold"
        ctx.font_size = 20
        ctx.rgb(1, 1, 1).move_to(0, -40).text("Tracking Number")
        
        # Digits drawing
        ctx.font = "Comic Mono"
        ctx.font_size = 28
        
        char_w = 22
        start_x = -110
        y_pos = 10
        
        text_str = "EMF-"
        
        # Draw "EMF-" static prefix
        for i in range(4):
            x_pos = start_x + i * char_w + (char_w / 2)
            ctx.rgb(0.7, 0.7, 0.7).move_to(x_pos, y_pos).text(text_str[i])
            
        # Draw the 6 customizable digits
        for i in range(6):
            char_idx = 4 + i
            x_pos = start_x + char_idx * char_w + (char_w / 2)
            is_active = (i == self.active_digit_index)
            
            if is_active:
                ctx.rgb(1, 0.8, 0)  # Highlight color (yellow)
                ctx.move_to(x_pos, y_pos).text(str(self.digits[i]))
                # Cursor underline
                ctx.line_width = 3
                ctx.move_to(x_pos - 8, y_pos + 16)
                ctx.line_to(x_pos + 8, y_pos + 16)
                ctx.stroke()
            else:
                ctx.rgb(1, 1, 1)    # White
                ctx.move_to(x_pos, y_pos).text(str(self.digits[i]))
                
        # Draw instructions
        ctx.font = "Arimo Regular"
        ctx.font_size = 11
        ctx.rgb(0.6, 0.6, 0.6)
        ctx.move_to(0, 48).text("A/D: Change Digit")
        ctx.move_to(0, 68).text("C: Next   E: Prev")
        ctx.move_to(0, 88).text("B: Recent Tracks")
        
        ctx.restore()

    def draw_recents(self, ctx):
        clear_background(ctx)
        ctx.save()
        
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        
        # Title
        ctx.font = "Arimo Bold"
        ctx.font_size = 20
        ctx.rgb(1, 1, 1).move_to(0, -50).text("Recent Tracks")
        
        if len(self.recents) == 0:
            ctx.font = "Arimo Regular"
            ctx.font_size = 16
            ctx.rgb(0.6, 0.6, 0.6).move_to(0, 10).text("No Recents")
        else:
            for i in range(len(self.recents)):
                y_pos = -20 + i * 20
                is_selected = (i == self.recents_selected_index)
                text_val = "EMF-" + self.recents[i]
                
                if is_selected:
                    ctx.rgb(1, 0.8, 0)  # Highlight color (yellow)
                    ctx.font = "Comic Mono"
                    ctx.font_size = 17
                    ctx.move_to(0, y_pos).text(text_val)
                    # Underline selected item
                    width = ctx.text_width(text_val)
                    ctx.line_width = 2
                    ctx.move_to(-width/2, y_pos + 10)
                    ctx.line_to(width/2, y_pos + 10)
                    ctx.stroke()
                else:
                    ctx.rgb(0.7, 0.7, 0.7)  # Dimmer color (white/gray)
                    ctx.font = "Comic Mono"
                    ctx.font_size = 15
                    ctx.move_to(0, y_pos).text(text_val)
                    
        # Bottom help
        ctx.font = "Arimo Regular"
        ctx.font_size = 11
        ctx.rgb(0.6, 0.6, 0.6)
        ctx.move_to(0, 76).text("C: Enter")
        ctx.move_to(0, 92).text("B: Enter Tracking Number")
        
        ctx.restore()

    def draw_loading(self, ctx):
        clear_background(ctx)
        ctx.save()
        
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        
        # Title
        ctx.font = "Arimo Bold"
        ctx.font_size = 20
        ctx.rgb(1, 1, 1).move_to(0, -40).text("Tracking Job")
        
        # Number we are tracking
        tracking_num = "".join(str(d) for d in self.digits)
        ctx.font = "Comic Mono"
        ctx.font_size = 24
        ctx.rgb(0.7, 0.7, 0.7).move_to(0, 0).text("EMF-" + tracking_num)
        
        # Loading feedback
        ctx.font = "Arimo Regular"
        ctx.font_size = 14
        ctx.rgb(0.3, 0.8, 1).move_to(0, 40).text("Fetching Data...")
        
        ctx.restore()

    def draw_result(self, ctx):
        clear_background(ctx)
        ctx.save()
        
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        
        # Safe extraction of attributes
        job = self.job_data or {}
        job_id = job.get("id", "EMF-XXXXXX")
        pickup = self._truncate(job.get("pickup_name", ""))
        delivery = self._truncate(job.get("delivery_name", ""))
        item = self._truncate(job.get("item_details", ""), max_len=18)
        status = str(job.get("status", "unknown")).upper()
        
        # Define status text colors dynamically
        if status == "DELIVERED":
            status_color = (0.1, 0.8, 0.1)  # Green
        elif status in ["ACCEPTED", "PICKED_UP", "ASSIGNED", "EN_ROUTE"]:
            status_color = (1, 0.6, 0)      # Orange/Yellow
        elif status in ["CANCELLED", "FAILED"]:
            status_color = (1, 0.2, 0.2)    # Red
        else:
            status_color = (0.2, 0.6, 1)    # Light Blue
            
        # 1. ID Header
        ctx.font = "Arimo Bold"
        ctx.font_size = 18
        ctx.rgb(1, 1, 1).move_to(0, -85).text(job_id)
        
        # 2. Item details
        ctx.font = "Arimo Regular"
        ctx.font_size = 12
        ctx.rgb(0.6, 0.6, 0.6).move_to(0, -60).text("ITEM")
        ctx.font = "Arimo Bold"
        ctx.font_size = 14
        ctx.rgb(1, 1, 1).move_to(0, -46).text(item)
        
        # 3. Pickup location (FROM)
        ctx.font = "Arimo Regular"
        ctx.font_size = 12
        ctx.rgb(0.6, 0.6, 0.6).move_to(0, -22).text("FROM")
        ctx.font = "Arimo Bold"
        ctx.font_size = 14
        ctx.rgb(1, 1, 1).move_to(0, -8).text(pickup)
        
        # 4. Delivery location (TO)
        ctx.font = "Arimo Regular"
        ctx.font_size = 12
        ctx.rgb(0.6, 0.6, 0.6).move_to(0, 16).text("TO")
        ctx.font = "Arimo Bold"
        ctx.font_size = 14
        ctx.rgb(1, 1, 1).move_to(0, 30).text(delivery)
        
        # 5. Delivery Status
        ctx.font = "Arimo Regular"
        ctx.font_size = 12
        ctx.rgb(0.6, 0.6, 0.6).move_to(0, 54).text("STATUS")
        ctx.font = "Arimo Bold"
        ctx.font_size = 15
        ctx.rgb(*status_color).move_to(0, 68).text(status)
        
        # 6. Navigation options
        ctx.font = "Arimo Regular"
        ctx.font_size = 11
        ctx.rgb(0.5, 0.5, 0.5).move_to(0, 95).text("C: Back  D: Reload")
        
        ctx.restore()

    def draw_error(self, ctx):
        clear_background(ctx)
        ctx.save()
        
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        
        # ID Header
        tracking_num = "".join(str(d) for d in self.digits)
        ctx.font = "Arimo Bold"
        ctx.font_size = 18
        ctx.rgb(1, 1, 1).move_to(0, -85).text("EMF-" + tracking_num)
        
        # Error Title
        ctx.font = "Arimo Bold"
        ctx.font_size = 20
        ctx.rgb(1, 0.2, 0.2).move_to(0, -30).text("Error")
        
        # Error description text
        error_msg = self._truncate(self.error_msg or "Unknown Error", max_len=24)
        ctx.font = "Arimo Regular"
        ctx.font_size = 14
        ctx.rgb(1, 1, 1).move_to(0, 15).text(error_msg)
        
        # Navigation options
        ctx.font = "Arimo Regular"
        ctx.font_size = 11
        ctx.rgb(0.5, 0.5, 0.5).move_to(0, 95).text("C: Back  D: Retry")
        
        ctx.restore()

    def draw(self, ctx):
        if self.state == "SPLASH":
            self.draw_splash(ctx)
        elif self.state == "INPUT":
            self.draw_input(ctx)
        elif self.state == "RECENTS":
            self.draw_recents(ctx)
        elif self.state in ["LOADING_DRAW", "LOADING_FETCH"]:
            self.draw_loading(ctx)
        elif self.state == "RESULT":
            self.draw_result(ctx)
        elif self.state == "ERROR":
            self.draw_error(ctx)

    def _cleanup(self):
        # Clean up listeners to avoid leaks/crashes when app is minimized or closed
        try:
            eventbus.remove(ButtonDownEvent, self._handle_buttondown, self)
        except Exception:
            pass

    def cleanup(self):
        self._cleanup()

__app_export__ = EMFExTracker
