import tkinter as tk
import time
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class CurveTempUI(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.start_time = time.time()
        self.time_data = []
        self.temp_data = []
        self.setpoint_data = []
        self.pwm_data = []

        self.figure = Figure(figsize=(5,4), dpi=100)
        self.ax_temp = self.figure.add_subplot(111)
        self.ax_temp.set_xlabel("Temps (s)")
        self.ax_temp.set_ylabel("Température (°C)", color="red")

        self.ax_pwm = self.ax_temp.twinx()
        self.ax_pwm.set_ylabel("PWM", color="blue")

        self.line_temp, = self.ax_temp.plot([], [], color="red", label="Température (°C)")
        self.line_setpoint, = self.ax_temp.plot([], [], "--", color="green", label="Consigne (°C)")
        self.line_pwm, = self.ax_pwm.plot([], [], color="blue", label="PWM")

        self.ax_temp.legend(loc="upper left")

        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        self.after(1000, self.update_plot)

    def add_data(self, temp, setpoint, pwm):
        t = time.time() - self.start_time
        self.time_data.append(t)
        self.temp_data.append(temp)
        self.setpoint_data.append(setpoint)
        self.pwm_data.append(pwm)

    def update_plot(self):
        self.line_temp.set_xdata(self.time_data)
        self.line_temp.set_ydata(self.temp_data)
        self.line_setpoint.set_xdata(self.time_data)
        self.line_setpoint.set_ydata(self.setpoint_data)
        self.line_pwm.set_xdata(self.time_data)
        self.line_pwm.set_ydata(self.pwm_data)

        self.ax_temp.relim()
        self.ax_temp.autoscale_view()
        self.ax_pwm.relim()
        self.ax_pwm.autoscale_view()

        self.canvas.draw()
        self.after(1000, self.update_plot)
