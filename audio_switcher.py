import tkinter as tk
from tkinter import messagebox
import warnings

import comtypes
from comtypes import GUID, HRESULT, COMMETHOD
from comtypes import CoCreateInstance, CLSCTX_ALL
from ctypes import c_int
from ctypes.wintypes import LPCWSTR, BOOL

from pycaw.pycaw import AudioUtilities, EDataFlow, DEVICE_STATE

warnings.filterwarnings(
    "ignore",
    message="COMError attempting to get property.*",
    category=UserWarning,
    module="pycaw.utils",
)

comtypes.CoInitialize()

# Windows audio role values
ERole_Console = 0
ERole_Multimedia = 1
ERole_Communications = 2


class IPolicyConfig(comtypes.IUnknown):
    """
    Undocumented Windows Core Audio interface used to change
    the default audio endpoint.
    """

    _iid_ = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")

    _methods_ = [
        COMMETHOD([], HRESULT, "GetMixFormat"),
        COMMETHOD([], HRESULT, "GetDeviceFormat"),
        COMMETHOD([], HRESULT, "ResetDeviceFormat"),
        COMMETHOD([], HRESULT, "SetDeviceFormat"),
        COMMETHOD([], HRESULT, "GetProcessingPeriod"),
        COMMETHOD([], HRESULT, "SetProcessingPeriod"),
        COMMETHOD([], HRESULT, "GetShareMode"),
        COMMETHOD([], HRESULT, "SetShareMode"),
        COMMETHOD([], HRESULT, "GetPropertyValue"),
        COMMETHOD([], HRESULT, "SetPropertyValue"),

        COMMETHOD(
            [],
            HRESULT,
            "SetDefaultEndpoint",
            (["in"], LPCWSTR, "wszDeviceId"),
            (["in"], c_int, "role"),
        ),

        COMMETHOD(
            [],
            HRESULT,
            "SetEndpointVisibility",
            (["in"], LPCWSTR, "wszDeviceId"),
            (["in"], BOOL, "visible"),
        ),
    ]


def set_default_audio_device(device_id: str):
    """
    Switch Windows default playback device for all common audio roles.
    """

    policy_config = CoCreateInstance(
        GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}"),
        IPolicyConfig,
        CLSCTX_ALL,
    )

    policy_config.SetDefaultEndpoint(device_id, ERole_Console)
    policy_config.SetDefaultEndpoint(device_id, ERole_Multimedia)
    policy_config.SetDefaultEndpoint(device_id, ERole_Communications)


def get_output_devices():
    """
    Return active Windows playback/output devices.
    """

    devices = []

    raw_devices = AudioUtilities.GetAllDevices()

    for device in raw_devices:
        # Only active playback/render devices
        if not device.state == DEVICE_STATE.ACTIVE.value:
            continue

        # pycaw uses DataFlow 0 for render/playback devices
        if device.data_flow != EDataFlow.eRender.value:
            continue

        devices.append(
            {
                "name": device.FriendlyName,
                "id": device.id,
            }
        )

    return devices


class AudioSwitcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows Audio Output Switcher")
        self.root.geometry("500x350")

        self.title_label = tk.Label(
            root,
            text="Select Audio Output",
            font=("Segoe UI", 16, "bold"),
        )
        self.title_label.pack(pady=15)

        self.device_frame = tk.Frame(root)
        self.device_frame.pack(fill="both", expand=True, padx=15)

        self.refresh_button = tk.Button(
            root,
            text="Refresh Devices",
            command=self.load_devices,
            height=2,
        )
        self.refresh_button.pack(fill="x", padx=15, pady=10)

        self.status_label = tk.Label(
            root,
            text="",
            anchor="w",
            font=("Segoe UI", 9),
        )
        self.status_label.pack(fill="x", padx=15, pady=(0, 10))

        self.load_devices()

    def clear_devices(self):
        for widget in self.device_frame.winfo_children():
            widget.destroy()

    def load_devices(self):
        self.clear_devices()

        try:
            devices = get_output_devices()
        except Exception as error:
            messagebox.showerror("Error", f"Could not read audio devices:\n\n{error}")
            return

        if not devices:
            self.status_label.config(text="No active output devices found.")
            return

        for device in devices:
            button = tk.Button(
                self.device_frame,
                text=device["name"],
                height=2,
                wraplength=440,
                command=lambda d=device: self.switch_device(d),
            )
            button.pack(fill="x", pady=5)

        self.status_label.config(text=f"Found {len(devices)} active output device(s).")

    def switch_device(self, device):
        try:
            set_default_audio_device(device["id"])
            self.status_label.config(text=f"Switched output to: {device['name']}")
        except Exception as error:
            messagebox.showerror(
                "Switch Failed",
                f"Could not switch to:\n\n{device['name']}\n\n{error}",
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = AudioSwitcherApp(root)
    root.mainloop()