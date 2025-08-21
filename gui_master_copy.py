
from tkinter import *
import tkinter as tk
from serialCom_Ctrl_fixed import SerialCtrl
import json
import numpy as np 
from functools import partial
from PIL import Image, ImageTk
import sys
import os
import pandas as pd
import configparser

class RootGUI:
    def __init__(self):
        self.root = Tk()
        self.root.title("VIBROTACTILE TRIALS")
        self.root.geometry("1000x1000")  # Adjusted to fit the new layout
        self.root.config(bg="light blue")


class ComGUI:
    def __init__(self, root, serialManager):
        self.root = root
        self.serialCtrl = serialManager
        self.frame = Frame(self.root, bg="pink")
        self.frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        self.label_title = Label(self.frame, text="COM MANAGER", font=("Helvetica", 14), bg="white", anchor="w")
        self.label_com = Label(self.frame, text="Available Ports:", font=("Helvetica", 10), width=15, anchor="w", bg="pink")
        self.label_bd = Label(self.frame, text="Baud Rate:", font=("Helvetica", 10), width=15, anchor="w", bg="pink")
        self.trial_gui=TrialGui(self.root,self.serialCtrl,self)

        self.ComOptionMenu()
        self.BaudMenu()

        self.btn_stop = Button(self.frame, text="Stop", width=10, state="active", command=self.serial_stop)

        self.setup_ui()

    def ComOptionMenu(self):
        self.serialCtrl.getCOMList()
        self.clicked_com = StringVar()
        self.clicked_com.set(self.serialCtrl.com_list[0])
        self.drop_com = OptionMenu(self.frame, self.clicked_com, *self.serialCtrl.com_list)
        self.drop_com.config(width=10)

    def BaudMenu(self):
        bauds = ["9600", "14400", "19200", "115200"]
        self.clicked_bd = StringVar()
        self.clicked_bd.set(bauds[0])
        self.drop_bd = OptionMenu(self.frame, self.clicked_bd, *bauds)
        self.drop_bd.config(width=10)

    def setup_ui(self):
        self.label_title.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        self.label_com.grid(row=1, column=0, sticky="w")
        self.drop_com.grid(row=1, column=1, sticky="e")
        self.label_bd.grid(row=2, column=0, sticky="w")
        self.drop_bd.grid(row=2, column=1, sticky="e")
        self.btn_stop.grid(row=3, column=0, columnspan=2, pady=10)

    def serial_stop(self):
        self.trial_gui.updating=False
        self.trial_gui.sliders_enabled=False
        period=self.trial_gui.slide_period.get()
        
        self.trial_gui.send_packet(motor1_duty=0, motor2_duty=0,period=period)

class TrialGui:
    def __init__(self, root, serialManager, comGUI):
        self.root = root
        self.serialCtrl = serialManager
        self.comGUI = comGUI
        self.updating = False
        self.current_mode = "linear"  # Default mode is linear
        self.skip_update_textbox = False  # Başlangıçta normal güncelleme açık
        # --- UI sadece timer (sistemden bağımsız) ---
        self.ui_timer_after_id = None
        self.ui_timer_default_seconds = 10   # istersen değiştir
        self.ui_timer_remaining = 0
        # Motor duty cycle initialization
        self.motor1 = 50
        self.motor2 = 50        
        # Initialize CombinedPlotGUI AFTER LinTrialGui is fully initialized
        self.combined_plot = CombinedPlotGUI(comGUI, root, serialManager, self)

        # Frame setup
        self.frame = Frame(self.root, bg="light green")
        self.title_frame = Frame(self.frame, bg="light green")
        self.label_title = Label(self.title_frame, text="TRIALS", font=("Helvetica", 15), bg="white", anchor="w")
        
        self.label_pwm1 = Label(self.frame, text="Motor 1 Duty", font=("Helvetica", 11), bg="light green", anchor="w")
        self.label_pwm2 = Label(self.frame, text="Motor 2 Duty", font=("Helvetica", 11), bg="light green", anchor="w")
        self.textbox = Text(self.frame, height=2, width=20)
        self.slide_pwm1 = tk.Scale(self.frame, from_=0, to=self.combined_plot.max_duty, orient=tk.HORIZONTAL, command=lambda value: self.update_slider(value),tickinterval=25)
        self.slide_pwm2 = tk.Scale(self.frame, from_=0, to=self.combined_plot.max_duty-1, orient=tk.HORIZONTAL, command=lambda value: self.update_slider(value),tickinterval=25)
        self.period_label=  Label(self.frame, text="Period", font=("Helvetica", 11), bg="light green", anchor="w")
        self.slide_period = tk.Scale(self.frame, from_=10, to=1000,resolution=5, orient=tk.HORIZONTAL,
                             command=lambda value: self.send_serially())
        self.ui_timer_label = Label(
    self.frame, text="Timer: -- s",
    font=("Helvetica", 11), bg="light green", anchor="w"
)
        # Add a button to toggle between modes
        self.button_toggle_mode = Button(self.frame, text="Toggle to Logarithmic", command=self.toggle_mode)
        self.update_button = Button(self.frame, text="Update Sliders", command=self.update_from_textbox)
        # Başlat ve Durdur butonları
        self.button_start = Button(self.frame, text="START", font=("Helvetica", 12), bg="green", fg="white", width=10, command=self.send_start_command)
        self.button_stop = Button(self.frame, text="STOP", font=("Helvetica", 12), bg="red", fg="white", width=10, command=self.send_stop_command)

        # Başlangıçta sliderlar pasif
        self.sliders_enabled = False

        # TrialGui içinde __init__ veya publish()'in sonuna ekle:
        self.snap_frame = Frame(self.frame, bg="light green")
       
        for val in [5,14,24,36,40,60,69,75,80]:
            
            btn = Button(self.snap_frame, text=str(val), command=lambda v=val: self.set_slider_to(v), width=4)
            btn.grid(row=9, column=val, padx=3)
            #btn.pack(side=LEFT, padx=3)
        btn = Button(self.snap_frame, text=str(48), command=lambda v=val: self.set_slider_to(48), width=4)
        btn.grid(row=9, column=50, padx=3)
        #btn.pack(side=LEFT, padx=3)
        # Publish UI
        self.publish()
        self.bind_keypad_events()

        
    def publish(self):
        self.frame.grid(row=0, column=0, rowspan=1, columnspan=1, padx=0, pady=0)
        self.title_frame.grid(row=1, column=7)
        self.label_title.grid(row=3, column=7)
        self.label_pwm1.grid(row=5, column=5)
        self.slide_pwm1.grid(row=5, column=6)
        self.label_pwm2.grid(row=6, column=5)
        self.slide_pwm2.grid(row=6, column=6)
        self.textbox.grid(row=8, column=6, padx=10, pady=10)
        self.period_label.grid(row=9, column=5)
        self.slide_period.grid(row=9, column=6)
        self.update_button.grid(row=8, column=7, padx=5, pady=10)   
        # Place the toggle button
        self.button_toggle_mode.grid(row=7, column=6, padx=10, pady=10)
        # En alta yerleştirebilirsin
        self.ui_timer_label.grid(row=7, column=6, padx=10, pady=10, sticky="w")

        self.button_start.grid(row=11, column=6, pady=(20, 5))
        self.button_stop.grid(row=12, column=6, pady=(0, 10))
        self.snap_frame.grid(row=10, column=6, pady=(10, 0))

    def get_motor_values(self):
        """Fetch complementary log and linear values for Motor1."""
        x_values = np.linspace(0, self.combined_plot.max_duty-2, self.combined_plot.max_duty+1)
        self.log_increasing, self.log_decreasing = self.combined_plot.calculate_logarithmic_values(x_values)
        lin_increasing, lin_decreasing = self.combined_plot.calculate_linear_values(x_values)
        self.lin_increasing = lin_increasing
        self.lin_decreasing=lin_decreasing

        motor1_value = int(round(self.motor1))  # Ensure motor1_value is an integer
    # ❗️Değer aralığını aşmasını önle:
        max_index = min(len(self.log_increasing) - 1, motor1_value)
        if motor1_value >= len(self.log_increasing):
            print(f"⚠️ motor1_value={motor1_value} > max_index={len(self.log_increasing)-1}, sınırlandı.")
        motor1_value = max_index
        closest_idx = np.abs(self.log_increasing - motor1_value).argmin()
        motor2_value = self.log_decreasing[closest_idx]

        #print(f"✅ Motor1 (Increasing) = {motor1_value}, Corrected Motor2 (Decreasing) = {motor2_value}")
        print(f"motor1_value: {motor1_value}, len(log_increasing): {len(self.log_increasing)}")
        return {
           
            "log_decreasing": motor2_value,
            "lin_decreasing": self.lin_decreasing[min(int(motor1_value), len(self.log_increasing)-1)],
            "log_increasing": self.log_increasing[min(int(motor1_value), len(self.log_increasing)-1)]
            


        }



    def toggle_mode(self):
        """Toggle between linear and logarithmic modes."""
        if self.current_mode == "linear":
            self.current_mode = "logarithmic"
            self.button_toggle_mode.config(text="Toggle to Linear")
        else:
            self.current_mode = "linear"
            self.button_toggle_mode.config(text="Toggle to Logarithmic")

        print(f"Mode changed to {self.current_mode}")

    def update_slider(self, value):
        """Update sliders based on the current mode."""
        if self.updating:
            return  # yeniden giriş engellensin

        if float(value) <1:
            print("⚠️ 1 sınırı aşıldı, değer 1'e ayarlandı.")
            self.slide_pwm1.set(1)
            self.motor1 = 1
            
        else:
            self.motor1 = float(value)
            


        self.motor1 = self.slide_pwm1.get()
        motor_values = self.get_motor_values()

        if self.current_mode == "linear":
            self.motor2 = motor_values["lin_decreasing"]
        elif self.current_mode == "logarithmic":
            self.motor2 = motor_values["log_decreasing"]
            self.motor1 = motor_values["log_increasing"]

        self.updating = True
        self.slide_pwm2.set(self.motor2)
        self.update_textbox()

        # ❗ START yapılmışsa veri gönder, yoksa sadece GUI güncelle
        if self.sliders_enabled:
            self.send_serially()
        else:
            print("🚫 START yapılmadı, sadece sliderlar güncellendi (veri gitmedi)")

        self.updating = False

        


    def set_slider_to(self, value):
        self.slide_pwm1.set(value)
        self.update_slider(value)

    def increase_period(self, event=None):
        
        new_value = min(1000, self.slide_period.get() + 10)
        self.slide_period.set(new_value)
        if self.sliders_enabled:
            self.send_serially()
            print(f"Period increased and sent: {new_value}")
        else:
            print(f"🕹️ Period increased to {new_value}, but not sent (START not pressed).")

    def decrease_period(self, event=None):
        
        new_value = max(0, self.slide_period.get() - 10)
        self.slide_period.set(new_value)
        if self.sliders_enabled:
            self.send_serially()
            print(f"Period decreased and sent: {new_value}")
        else:
            print(f"🕹️ Period decreased to {new_value}, but not sent (START not pressed).")
        period=self.slide_period.get()
        self.send_packet(period=period)
       
        
       
    
    def ui_timer_start(self, seconds=None):
        """Sadece etikette geri sayım. Sisteme etki etmez."""
        # varsa önceki zamanı iptal et (üst üste başlamasın)
        if self.ui_timer_after_id is not None:
            try:
                self.root.after_cancel(self.ui_timer_after_id)
            except Exception:
                pass
            self.ui_timer_after_id = None

        if seconds is None:
            seconds = self.ui_timer_default_seconds

        self.ui_timer_remaining = int(seconds)
        self._ui_timer_tick()

    def _ui_timer_tick(self):
        # Etiketi güncelle
        self.ui_timer_label.config(text=f"Timer: {self.ui_timer_remaining} s")

        # 0'a geldi mi durdur
        if self.ui_timer_remaining <= 0:
            self.ui_timer_after_id = None
            return

        # 1 sn sonra tekrar
        self.ui_timer_remaining -= 1
        self.ui_timer_after_id = self.root.after(1000, self._ui_timer_tick)

    def ui_timer_reset(self):
        """İstersen dışarıdan sıfırlamak için (kullanmak zorunda değilsin)."""
        if self.ui_timer_after_id is not None:
            try:
                self.root.after_cancel(self.ui_timer_after_id)
            except Exception:
                pass
            self.ui_timer_after_id = None
        self.ui_timer_label.config(text="Timer: -- s")


    # Other methods remain unchanged...
    def send_start_command(self):
        self.ui_timer_start(seconds=10)  # istersen bu değeri değiştir

        self.sliders_enabled = True
        self.slide_pwm1.config(state="normal")
        self.slide_pwm2.config(state="normal")
        self.slide_period.config(state="normal")  # Eğer period slider'ı da açılmalıysa
      
        
        self.serialCtrl.SerialOpen(ComGUI=self.comGUI)
        self.send_packet()
        print("✅ START: Sliderlar aktif")

    def send_stop_command(self):
        self.sliders_enabled = False
        self.send_packet(motor1_duty=0, motor2_duty=0)
        print("🛑 STOP: Sliderlar pasif")



    def bind_keypad_events(self):
        """Bind the Up/Down keys for logarithmic control and Right/Left keys for linear control."""
        self.root.bind("<Up>", self.handle_increase_logarithmic)
        self.root.bind("<Down>", self.handle_decrease_logarithmic)
        self.root.bind("<Right>",self.increase_period)
        self.root.bind("<Left>",self.decrease_period)
        self.textbox.bind("<Return>", self.update_from_textbox_event)
    
    def update_from_textbox_event(self, event):
        self.skip_update_textbox = True  # 🚩 textbox güncellemesini geçici kapat
        self.update_from_textbox()
        return "break"



        

    def handle_increase_logarithmic(self, event=None):
        """Increase Motor 1 using logarithmic values (Up Key)."""
        self.update_motor(mode="logarithmic", motor=1, increment=True)

    def handle_decrease_logarithmic(self, event=None):
        """Decrease Motor 1 using logarithmic values (Down Key)."""
        self.update_motor(mode="logarithmic", motor=1, increment=False)

    def handle_increase_linear(self, event=None):
        """Increase Motor 2 using linear values (Right Key)."""
        self.update_motor(mode="linear", motor=2, increment=True)

    def handle_decrease_linear(self, event=None):
        """Decrease Motor 2 using linear values (Left Key)."""
        self.update_motor(mode="linear", motor=2, increment=False)



    def update_motor(self, mode, motor, increment):
        """
        Update the duty cycle of the given motor based on the specified mode.
        mode: "logarithmic" or "linear"
        motor: 1 for Motor 1 (slider_pwm1), 2 for Motor 2 (slider_pwm2)
        increment: True to increase, False to decrease
        """
        if motor == 1:  # Adjust Motor 1
            if increment:
                self.slide_pwm1.set(min(1000, self.slide_pwm1.get() + 1))
            else:
                self.slide_pwm1.set(max(0, self.slide_pwm1.get() - 1))

            # Dynamically calculate Motor 2's value based on mode
            motor_values = self.get_motor_values()
            if mode == "logarithmic":
                self.motor2 = motor_values["log_decreasing"]
            elif mode == "linear":
                self.motor2 = motor_values["lin_decreasing"]
            self.slide_pwm2.set(self.motor2)

        elif motor == 2:  # Adjust Motor 2
            if increment:
                self.slide_pwm2.set(min(80, self.slide_pwm2.get() + 1))
            else:
                self.slide_pwm2.set(max(0, self.slide_pwm2.get() - 1))

            # Dynamically calculate Motor 1's value based on mode
            motor_values = self.get_motor_values()
            if mode == "logarithmic":
                self.motor1 = motor_values["log_increasing"]
            elif mode == "linear":
                self.motor1 = motor_values["lin_increasing"]
            self.slide_pwm1.set(self.motor1)

        # Update the UI and send updated values
        self.update_textbox()
        self.send_serially()



    

    def update_textbox(self):
        """Update the textbox with motor1 and motor2 values."""
        if self.skip_update_textbox:
            return  # 🚫 Eğer flag aktifse textbox'a hiç dokunma
        #motor1 = self.slide_pwm1.get()
        #motor2 = self.slide_pwm2.get()
        self.textbox.delete("1.0", tk.END)
        #self.textbox.insert("1.0", f"{motor1}\n{motor2}")
        


    def update_from_textbox(self):
        try:
            values = self.textbox.get("1.0", tk.END).strip().split("\n")
            motor1 = int(values[0]) if len(values) > 0 else 0
            self.motor1 = motor1

            # geçici olarak komutu durdur
            self.slide_pwm1.configure(command=None)
            self.slide_pwm2.configure(command=None)

            if 0 <= motor1 <= 100:
                self.slide_pwm1.set(motor1)
            
            motor_values = self.get_motor_values()
            self.motor2 = motor_values["log_decreasing"]

            if 0 <= self.motor2 <= 100:
                self.slide_pwm2.set(self.motor2)

            self.textbox.delete("1.0", tk.END)
            self.send_serially()

        except ValueError:
            print("Invalid input in textbox")
            self.textbox.delete("1.0", tk.END)

        finally:
            # ✅ yeniden bağla
            self.slide_pwm1.configure(command=lambda value: self.update_slider(value))
            self.slide_pwm2.configure(command=lambda value: self.update_slider(value))




    def handle_plot_selection(self, motor1_value, motor2_value):
        """Update sliders and textbox when a plot point is selected."""
        self.updating = True
        self.slide_pwm1.set(motor1_value)
        self.slide_pwm2.set(motor2_value)
        self.update_textbox()
        self.send_serially()
        self.updating = False

    def send_packet(self,motor1_duty=None,motor2_duty=None,period=None):
        import json

        def coerce_int(val, fallback):
            # None, "" veya sayıya çevrilemeyen bir şey gelirse fallback kullan
            if val is None:
                return int(fallback)
            try:
                # "123.0" gibi stringler için de çalışsın
                return int(float(val))
            except Exception:
                return int(fallback)

        m1 = coerce_int(motor1_duty, self.slide_pwm1.get())
        m2 = coerce_int(motor2_duty, self.slide_pwm2.get())
        per = coerce_int(period, self.slide_period.get())

        if motor1_duty is None: motor1_duty = int(self.slide_pwm1.get())
        if motor2_duty is None: motor2_duty = int(self.slide_pwm2.get())
        if period is None: int(self.slide_period.get())
        payload = {
        "cmd": "set",
        "deney_no": 1,
        "mode": self.current_mode,
        "motor1_duty": m1,
        "motor2_duty": m2,
        "period": per,
    }
        self.serialCtrl.send_json(payload)


    def send_serially(self):
        """Send updated motor values via serial only if started."""
        if not self.sliders_enabled:
            print("🚫 START basılmadı, veri gönderilmiyor.")
            return  # START'a basılmadıysa gönderme
        self.send_packet()
    
    def update_sliders_and_text(self, motor1_value, motor2_value):
        self.updating = True
        self.slide_pwm1.set(motor1_value)
        self.slide_pwm2.set(motor2_value)

        self.textbox.delete("1.0", tk.END)
        self.textbox.insert("1.0", f"{motor1_value}\n{motor2_value}")

        self.updating = False


    def send_selected_values(self, motor1_value, motor2_value):
        
        try:
            # Ensure serial communication is open and send the data
            self.send_packet(motor1_value,motor2_value) 

            # Update sliders and text with the selected values
            self.update_sliders_and_text(motor1_value, motor2_value)

            # Log the action
            #print(f"Selected from {plot_type} plot: {data_json}")

        except Exception as e:
            print(f"Error sending selected values: {e}")

   


class CombinedPlotGUI:
    def __init__(self, comGUI, root, serialManager, trial_gui):
        self.root = root
        self.comGUI = comGUI
        self.serialCtrl = serialManager
        self.trial_gui = trial_gui
        self.max_duty = self.load_config()
        # Frame setup
        self.frame = Frame(root, bg="white")
        self.frame.grid(row=0, column=3, padx=10, pady=10, sticky="n")

        # Canvas dimensions
        self.canvas_width = 450
        self.canvas_height = 450
        self.padding = 50

        # Canvas for logarithmic plot
        self.plot_canvas = tk.Canvas(self.frame, bg="white", width=self.canvas_width, height=self.canvas_height)
        self.plot_canvas.grid(row=0, column=0)
        self.log_point_mapping = {}  # To map item IDs to logical logarithmic data

        # Canvas for linear plot
        self.plot_canvas1 = tk.Canvas(self.frame, bg="white", width=self.canvas_width, height=self.canvas_height)
        self.plot_canvas1.grid(row=1, column=0)
        self.lin_point_mapping = {}  # To map item IDs to logical linear data

        # Initial plotting
        self.update_plot(trial_gui.motor1, trial_gui.motor2)

    def calculate_linear_values(self, x_values):
        A = [i * (self.max_duty ) + 1 for i in np.linspace(0, 1, len(x_values))]  # 1 to 81
        B = [self.max_duty - i for i in A]  # complementary: 80 to 0
        return A, B
            #print(lin_decreasing)
           
            
            
   
    def calculate_logarithmic_values(self, _=None):
        # Convert input to a NumPy array
       
        x_p = np.linspace(0, 1, self.max_duty)

        # Define the logarithmic equations for I_0^g and I_1^g
        I_0_g = np.log(2 - x_p) / np.log(2)
        # I_1_g = np.log(1 + x_p) / np.log(2)
        I_1_g = np.flip(I_0_g)

        # Compute logarithmic h1 and h2 values (scaled from 1 to 100)
        self.log_h1_values = np.round(I_0_g * (self.max_duty-2) + 2).astype(int)
        self.log_h2_values = np.round(I_1_g * (self.max_duty-2) + 2).astype(int)

        # Create a DataFrame for visualization
        df = pd.DataFrame({
    'Index': np.arange(1, len(self.log_h1_values) + 1),
    'log_h1': self.log_h1_values,
    'log_h2': self.log_h2_values
})
        return self.log_h1_values, self.log_h2_values

        # Print the table
        #print(df)

        # Print debugging values
        #for i, (log_inc, log_dec) in enumerate(zip(log_h1_values, log_h2_values)):
         #   print(f"Index {i}: log_increasing = {log_inc}, log_decreasing = {log_dec}")

       





    def update_plot(self, motor1=None, motor2=None):
        """Redraw both plots based on the active model."""
        if motor1 is None:
            motor1 = self.trial_gui.motor1
        if motor2 is None:
            motor2 = self.trial_gui.motor2

        self.plot_canvas.delete("all")
        self.plot_canvas1.delete("all")

        # Generate x-values (100 points)
        x_values = np.arange(0,self.max_duty)  # Ensuring 100 elements

        # Calculate values
        lin_increasing, lin_decreasing = self.calculate_linear_values(x_values)
        log_increasing, log_decreasing = self.calculate_logarithmic_values()

        # Ensure all arrays are exactly 100 elements
        lin_increasing, lin_decreasing = np.array(lin_increasing[:100]), np.array(lin_decreasing[:100])
        log_increasing, log_decreasing = np.array(log_increasing[:self.max_duty]), np.array(log_decreasing[:self.max_duty])
        print(log_increasing)
        print(log_decreasing)
        # Draw plots
        self.draw_plot(self.plot_canvas, x_values, log_increasing, log_decreasing, self.log_point_mapping)
        self.draw_plot(self.plot_canvas1, x_values, lin_increasing, lin_decreasing, self.lin_point_mapping)

  

    def draw_axes(self, canvas, grid='y'):
        """Draws X and Y axes with optional grid lines.

        grid: 'both', 'x', 'y', or 'none'
        """
        # Eksen çizgileri
        canvas.create_line(self.padding, self.canvas_height - self.padding,
                        self.canvas_width - self.padding, self.canvas_height - self.padding,
                        fill="black", width=2)  # X-axis
        canvas.create_text(self.canvas_width - self.padding + 6,
                        self.canvas_height - self.padding,
                        text="Duty1", anchor="w", font=("Helvetica", 8))

        canvas.create_line(self.padding, self.padding,
                        self.padding, self.canvas_height - self.padding,
                        fill="black", width=2)  # Y-axis
        canvas.create_text(self.padding + 10, self.padding - 5,
                        text="Duty2", anchor="e", font=("Helvetica", 8))

        # Grid çizgileri ve etiketler
        for i in [5,14,24,36,40,60,69,75,80]:
            x_pos = self.padding + (i / 100) * (self.canvas_width - 2 * self.padding)
            y_pos = self.canvas_height - self.padding - (i / 100) * (self.canvas_height - 2 * self.padding)

            if grid in ['both', 'x']:
                canvas.create_line(x_pos, self.padding, x_pos, self.canvas_height - self.padding,
                                fill="gray", dash=(2, 2))
                canvas.create_text(x_pos, self.canvas_height - self.padding + 10,
                                text=str(i), anchor="n", font=("Helvetica", 8))

            if grid in ['both', 'y']:
                canvas.create_line(self.padding, y_pos, self.canvas_width - self.padding, y_pos,
                                fill="gray", dash=(2, 2))
                canvas.create_text(self.padding - 10, y_pos,
                                text=str(i), anchor="e", font=("Helvetica", 8))

                


    def draw_plot(self, canvas, x_values, increasing_values, decreasing_values, point_mapping):
        """Draws the motor duty cycle plots with axes."""
        # Clear the canvas before drawing
        canvas.delete("all")

        # Draw the axes first
        self.draw_axes(canvas)

        # Draw the actual curves
        for i in range(len(x_values) - 1):
          
            x1 = self.padding + (x_values[i] /100) * (self.canvas_width - 2 * self.padding)
            x2 = self.padding + (x_values[i + 1] / 100) * (self.canvas_width - 2 * self.padding)
               
            y1_inc = self.canvas_height - self.padding - (increasing_values[i] / 100) * (self.canvas_height - 2 * self.padding)
            y2_inc = self.canvas_height - self.padding - (increasing_values[i + 1] /100) * (self.canvas_height - 2 * self.padding)

            y1_dec = self.canvas_height - self.padding - (decreasing_values[i] /100) * (self.canvas_height - 2 * self.padding)
            y2_dec = self.canvas_height - self.padding - (decreasing_values[i + 1] / 100) * (self.canvas_height - 2 * self.padding)

            # Draw the increasing and decreasing motor duty curves
            canvas.create_line(x1, y1_inc, x2, y2_inc, fill="blue", width=2)
            canvas.create_line(x1, y1_dec, x2, y2_dec, fill="red", width=2)

        # Add interactive points on the curves
        for x, y in zip(x_values, increasing_values):
            self.create_active_point(canvas, x, y, point_mapping, "blue")
        for x, y in zip(x_values, decreasing_values):
            self.create_active_point(canvas, x, y, point_mapping, "red")


            
    def create_active_point(self, canvas, x, y, point_mapping, color):
        """Create an active oval point on the canvas."""
        canvas_x = (self.padding + (x / 100) * (self.canvas_width - 2 * self.padding))
        canvas_y = (self.canvas_height - self.padding - (y / 100) * (self.canvas_height - 2 * self.padding))

        # Create an oval (point) on the canvas at (canvas_x, canvas_y)
        point_id = canvas.create_oval(canvas_x - 2, canvas_y - 2, canvas_x + 2, canvas_y + 2, fill=color, outline="")
 
        point_mapping[point_id] = (x, y)
        print(f"mot1:{x},mot2:{y}")
        

        canvas.tag_bind(point_id, "<Button-1>", lambda e, id=point_id: self.on_point_clicked(id, point_mapping))

       

    def on_point_clicked(self, point_id, point_mapping):
        """Ensure that the clicked point correctly maps to the complementary log value."""
            
        x_values = np.linspace(1, (self.max_duty+1),(self.max_duty+1))
        log_increasing, log_decreasing = self.calculate_logarithmic_values(x_values)
        lin_increasing, lin_decreasing = self.calculate_linear_values(x_values)
        # index is position on x axes in the graph
        idx, _ = point_mapping[point_id]  
        # because graph is 0 to 100 and log_* are also 0 to 100 we can use index directly
        if self.trial_gui.current_mode == "logarithmic":
            motor1_value = log_increasing[int(idx)]        
            motor2_value = log_decreasing[int(idx)]
            print(motor1_value)
            print(motor2_value)
            print(f"idx:{idx}")

        elif self.trial_gui.current_mode == "linear":
            motor1_value = lin_increasing[int(idx)]        
            motor2_value = lin_decreasing[int(idx)]
            print(motor1_value)
            print(motor2_value)
            print(f"idx:{idx}")
            
        


        '''
        if motor1_value in log_increasing:
            motor2_value = log_decreasing[np.where(log_increasing == motor1_value)][0]
        else:
            closest_idx = np.abs(log_increasing - motor1_value).argmin()
            motor2_value = log_decreasing[closest_idx]

        print(f"✔️ Selected Complementary Motor2: {motor2_value} for Motor1: {motor1_value}")

        # Ensure motor2_value is an integer before setting the slider
        motor2_value = int(motor2_value)
        '''

        self.trial_gui.slide_pwm1.set(motor1_value)
        self.trial_gui.slide_pwm2.set(motor2_value)
        self.trial_gui.update_textbox()
        self.trial_gui.send_serially()

    def resource_path(self,relative_path):
        try:
            # PyInstaller kullanıyorsan exe çalışınca buraya düşer
            base_path = sys._MEIPASS
        except Exception:
            # Normal çalışıyorsa buraya
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def load_config(self):
        config = configparser.ConfigParser()
        config.read(self.resource_path('config.ini'))
        return int(config['settings']['max_duty'])


class ButtonGUI:
    
    def __init__(self, comGUI, root, serialManager, trial_gui):
        self.root = root
        self.comGUI = comGUI
        self.serialCtrl = serialManager
        self.trial_gui = trial_gui
        self.trial_count = 1  # İlk deneme numarası
        self.frame = Frame(self.root, bg="light green")
        self.frame.grid(row=0, column=4)
        self.position_buttons={}
        self.save_button=Button(self.frame,text="Save to CSV",font=("Helvetica", 11), command= self.save_to_csv, width=15)
        self.label_name=Label(self.frame,text="Participant Name:",font=("Helvetica", 11),bg="light green")
        self.label_mid=Label(self.frame,text="Midpoint:",font=("Helvetica", 12),bg="light green")
        self.label_mid.grid(row=5,column=3)
        self.label_name.grid(row=12,column=4,pady=(10,0),sticky='n')
        self.entry_name=Entry(self.frame,width=20,font=("Helvetica", 11))
        self.entry_name.grid(row=13,column=4,pady=(0,10),sticky='n')
        # Ensure the Save button remains in its own position and image is above it
        self.save_button.grid(row=11, column=4, pady=5)
        self.put_image()
        for i in range(1,10):
            
            self.position_buttons[i]=Button(self.frame,text=f"Value:{i}",font=("Helvetica", 11), command= partial(self.select_position, i),width=10)
            self.position_buttons[i].grid(row=i, column=4, pady=5, sticky="n") 
            
        
       

        self.selected_position = None  
        # # Add buttons for manual control
        # self.button1 = Button(self.frame, text="wrist(1)", command=lambda: self.write_value(1), width=10)
        # self.button1.pack()
        # self.button4 = Button(self.frame, text="4", command=lambda: self.write_value(4), width=10)
        # self.button4.pack()
        # self.button5 = Button(self.frame, text="Middle(5)", command=lambda: self.write_value(5), width=10)      
        # self.button9 = Button(self.frame, text="Elbow(9)", command=lambda: self.write_value(9), width=10)
        # self.button9.pack()
    def select_position(self,pos):

        self.selected_position=pos
        #print(f"Sensed Position:{self.selected_position}")

    def save_to_csv(self):
        participant_name=self.entry_name.get().strip()#
        if not participant_name:
            print("Please Enter Participant Name!")
            return
        if self.selected_position is not None :
            motor1_duty = self.trial_gui.slide_pwm1.get()
            motor2_duty = self.trial_gui.slide_pwm2.get()

            # Save to CSV
            import csv
            with open('motor_data.csv', mode='a', newline='') as file:
                writer = csv.writer(file)
                # Write data to the CSV file
                writer.writerow([self.trial_count,participant_name,motor1_duty, motor2_duty, self.selected_position,self.trial_gui.current_mode])
                print(f"{self.trial_count} Saved: Person: {participant_name}, Duty1: {motor1_duty}, Duty2: {motor2_duty}, Position: {self.selected_position}")
                self.trial_count+=1
        else:
            print("Please select a position and a value before saving.")
    def resource_path(self,relative_path):
        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    def put_image(self):
        image=Image.open(self.resource_path("el.webp"))     
        image=image.resize((200,200))
        self.img=ImageTk.PhotoImage(image)
        self.label=Label(self.frame,image=self.img)
        self.label.grid(row=0, column=4, pady=(0, 5),sticky="n") 
        image1=Image.open(self.resource_path("dirsek.jpg"))    
        image1=image1.resize((100,100))
        self.img1=ImageTk.PhotoImage(image1)
        self.label1=Label(self.frame,image=self.img1)
        self.label1.grid(row=10, column=4, pady=5, sticky="n")

        # Ensure the Save button remains in its own position
        self.save_button.grid(row=11, column=4, pady=(5, 5), sticky="n")
        
        
        
    def write_value(self,text):
        print(text)
# Main Function
if __name__ == "__main__":
    serialCtrl = SerialCtrl()  # Placeholder for your SerialCtrl implementation
    gui = RootGUI()
    com_gui = ComGUI(gui.root, serialCtrl)
    trigui=TrialGui(gui.root, serialCtrl, com_gui)
    ButtonGUI(com_gui,gui.root,serialCtrl,trigui)
    gui.root.mainloop()
