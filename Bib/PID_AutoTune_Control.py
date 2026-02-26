import time

class PID_ATune:
    def __init__(self, input_callback, output_callback):
        self.input = input_callback
        self.output = output_callback
        self.controlType = 0  # default to PI
        self.noiseBand = 0.5
        self.running = False
        self.oStep = 30
        self.SetLookbackSec(10)
        self.lastTime = time.time() * 1000  # Convert to milliseconds
        self.peakType = 0
        self.peakCount = 0
        self.justchanged = False
        self.absMax = 0
        self.absMin = 0
        self.setpoint = 0
        self.outputStart = 0
        self.lastInputs = [0] * 100  # Assuming a maximum lookback of 100
        self.nLookBack = 40  # Default value for 10 seconds
        self.sampleTime = 250  # Default sample time in milliseconds
        self.peaks = [0] * 10
        self.peak1 = 0
        self.peak2 = 0
        self.Ku = 0
        self.Pu = 0
        self.current_output = 0  # Stocke la valeur actuelle de la sortie

    def Cancel(self):
        self.running = False

    def Runtime(self):
        self.justevaled = False
        if self.peakCount > 9 and self.running:
            self.running = False
            self.FinishUp()
            return 1

        now = time.time() * 1000  # Convert to milliseconds
        if (now - self.lastTime) < self.sampleTime:
            return 0
        self.lastTime = now

        refVal = self.input()
        self.justevaled = True

        if not self.running:
            # Initialize working variables the first time around
            self.peakType = 0
            self.peakCount = 0
            self.justchanged = False
            self.absMax = refVal
            self.absMin = refVal
            self.setpoint = refVal
            self.running = True
            self.outputStart = self.current_output
            self.current_output = self.outputStart + self.oStep
            self.output(self.current_output)  # Applique la nouvelle sortie
        else:
            if refVal > self.absMax:
                self.absMax = refVal
            if refVal < self.absMin:
                self.absMin = refVal

        # Oscillate the output based on the input's relation to the setpoint
        if refVal > self.setpoint + self.noiseBand:
            self.current_output = self.outputStart - self.oStep
        elif refVal < self.setpoint - self.noiseBand:
            self.current_output = self.outputStart + self.oStep
        self.output(self.current_output)  # Applique la nouvelle sortie

        # Identify peaks
        isMax = True
        isMin = True
        for i in range(self.nLookBack - 1, -1, -1):
            val = self.lastInputs[i]
            if isMax:
                isMax = refVal > val
            if isMin:
                isMin = refVal < val
            self.lastInputs[i + 1] = self.lastInputs[i]
        self.lastInputs[0] = refVal

        if self.nLookBack < 9:
            return 0

        if isMax:
            if self.peakType == 0:
                self.peakType = 1
            if self.peakType == -1:
                self.peakType = 1
                self.justchanged = True
                self.peak2 = self.peak1
            self.peak1 = now
            self.peaks[self.peakCount] = refVal
        elif isMin:
            if self.peakType == 0:
                self.peakType = -1
            if self.peakType == 1:
                self.peakType = -1
                self.peakCount += 1
                self.justchanged = True
            if self.peakCount < 10:
                self.peaks[self.peakCount] = refVal

        if self.justchanged and self.peakCount > 2:
            # Check if we can autotune based on the last peaks
            avgSeparation = (abs(self.peaks[self.peakCount - 1] - self.peaks[self.peakCount - 2]) + abs(self.peaks[self.peakCount - 2] - self.peaks[self.peakCount - 3])) / 2
            if avgSeparation < 0.05 * (self.absMax - self.absMin):
                self.FinishUp()
                self.running = False
                return 1

        self.justchanged = False
        return 0

    def FinishUp(self):
        self.current_output = self.outputStart
        self.output(self.current_output)  # Applique la sortie finale
        # Generate tuning parameters
        self.Ku = 4 * (2 * self.oStep) / ((self.absMax - self.absMin) * 3.14159)
        self.Pu = (self.peak1 - self.peak2) / 1000

    def GetKp(self):
        return 0.6 * self.Ku if self.controlType == 1 else 0.4 * self.Ku

    def GetKi(self):
        return (1.2 * self.Ku / self.Pu) if self.controlType == 1 else (0.48 * self.Ku / self.Pu)

    def GetKd(self):
        return (0.075 * self.Ku * self.Pu) if self.controlType == 1 else 0

    def SetOutputStep(self, Step):
        self.oStep = Step

    def GetOutputStep(self):
        return self.oStep

    def SetControlType(self, Type):  # 0=PI, 1=PID
        self.controlType = Type

    def GetControlType(self):
        return self.controlType

    def SetNoiseBand(self, Band):
        self.noiseBand = Band

    def GetNoiseBand(self):
        return self.noiseBand

    def SetLookbackSec(self, value):
        if value < 1:
            value = 1
        if value < 25:
            self.nLookBack = value * 4
            self.sampleTime = 250
        else:
            self.nLookBack = 100
            self.sampleTime = value * 10

    def GetLookbackSec(self):
        return self.nLookBack * self.sampleTime / 1000