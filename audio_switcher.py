import signal
import sys
import tkinter as tk
from tkinter import messagebox

import comtypes
from comtypes import GUID, HRESULT, COMMETHOD
from comtypes import CoCreateInstance, CLSCTX_ALL

from ctypes import (
    POINTER,
    Structure,
    Union,
    c_ulong,
    c_ushort,
    c_int,
    c_void_p,
)
from ctypes.wintypes import DWORD, LPCWSTR, LPWSTR, BOOL


# ------------------------------------------------------------
# Windows Core Audio constants
# ------------------------------------------------------------

DEVICE_STATE_ACTIVE = 0x00000001

# Audio data flow
eRender = 0  # Playback/output devices

# Windows audio roles
ERole_Console = 0
ERole_Multimedia = 1
ERole_Communications = 2

STGM_READ = 0x00000000

# PROPVARIANT type for string values
VT_LPWSTR = 31


# ------------------------------------------------------------
# PROPERTYKEY / PROPVARIANT definitions
# ------------------------------------------------------------

class PROPERTYKEY(Structure):
    _fields_ = [
        ("fmtid", GUID),
        ("pid", DWORD),
    ]


class PROPVARIANT_UNION(Union):
    _fields_ = [
        ("pwszVal", LPWSTR),
        ("pointerValue", c_void_p),
    ]


class PROPVARIANT(Structure):
    _anonymous_ = ("u",)

    _fields_ = [
        ("vt", c_ushort),
        ("wReserved1", c_ushort),
        ("wReserved2", c_ushort),
        ("wReserved3", c_ushort),
        ("u", PROPVARIANT_UNION),
    ]


# PKEY_Device_FriendlyName
PKEY_Device_FriendlyName = PROPERTYKEY(
    GUID("{a45c254e-df1c-4efd-8020-67d146a850e0}"),
    14,
)


# ------------------------------------------------------------
# COM Interfaces
# ------------------------------------------------------------

class IPropertyStore(comtypes.IUnknown):
    _iid_ = GUID("{886d8eeb-8cf2-4446-8d02-cdba1dbdcf99}")

    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "GetCount",
            (["out"], POINTER(DWORD), "cProps"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetAt",
            (["in"], DWORD, "iProp"),
            (["out"], POINTER(PROPERTYKEY), "pkey"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetValue",
            (["in"], POINTER(PROPERTYKEY), "key"),
            (["out"], POINTER(PROPVARIANT), "pv"),
        ),
        COMMETHOD([], HRESULT, "SetValue"),
        COMMETHOD([], HRESULT, "Commit"),
    ]


class IMMDevice(comtypes.IUnknown):
    _iid_ = GUID("{d666063f-1587-4e43-81f1-b948e807363f}")

    _methods_ = [
        COMMETHOD([], HRESULT, "Activate"),
        COMMETHOD(
            [],
            HRESULT,
            "OpenPropertyStore",
            (["in"], DWORD, "stgmAccess"),
            (["out"], POINTER(POINTER(IPropertyStore)), "ppProperties"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetId",
            (["out"], POINTER(LPCWSTR), "ppstrId"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetState",
            (["out"], POINTER(DWORD), "pdwState"),
        ),
    ]


class IMMDeviceCollection(comtypes.IUnknown):
    _iid_ = GUID("{0bd7a1be-7a1a-44db-8397-cc5392387b5e}")

    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "GetCount",
            (["out"], POINTER(c_ulong), "pcDevices"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "Item",
            (["in"], c_ulong, "nDevice"),
            (["out"], POINTER(POINTER(IMMDevice)), "ppDevice"),
        ),
    ]


class IMMDeviceEnumerator(comtypes.IUnknown):
    _iid_ = GUID("{a95664d2-9614-4f35-a746-de8db63617e6}")

    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "EnumAudioEndpoints",
            (["in"], c_int, "dataFlow"),
            (["in"], DWORD, "dwStateMask"),
            (["out"], POINTER(POINTER(IMMDeviceCollection)), "ppDevices"),
        ),
        COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint"),
        COMMETHOD([], HRESULT, "GetDevice"),
        COMMETHOD([], HRESULT, "RegisterEndpointNotificationCallback"),
        COMMETHOD([], HRESULT, "UnregisterEndpointNotificationCallback"),
    ]


class IPolicyConfig(comtypes.IUnknown):
    """
    Undocumented Windows interface used to change the default audio endpoint.
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


# ------------------------------------------------------------
# Audio device logic
# ------------------------------------------------------------

def get_device_name(device):
    store = device.OpenPropertyStore(STGM_READ)
    prop = store.GetValue(PKEY_Device_FriendlyName)

    if prop.vt == VT_LPWSTR and prop.pwszVal:
        return str(prop.pwszVal)

    return "Unknown Audio Device"


def get_device_id(device):
    return device.GetId()


def get_output_devices():
    devices = []

    enumerator = CoCreateInstance(
        GUID("{bcde0395-e52f-467c-8e3d-c4579291692e}"),
        IMMDeviceEnumerator,
        CLSCTX_ALL,
    )

    collection = enumerator.EnumAudioEndpoints(
        eRender,
        DEVICE_STATE_ACTIVE,
    )

    count = collection.GetCount()

    for index in range(count):
        try:
            device = collection.Item(index)

            name = get_device_name(device)
            device_id = get_device_id(device)

            devices.append(
                {
                    "name": name,
                    "id": device_id,
                }
            )

        except Exception as error:
            print(f"Skipped audio device {index}: {error}")

    return devices


def set_default_audio_device(device_id):
    policy_config = CoCreateInstance(
        GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}"),
        IPolicyConfig,
        CLSCTX_ALL,
    )

    policy_config.SetDefaultEndpoint(device_id, ERole_Console)
    policy_config.SetDefaultEndpoint(device_id, ERole_Multimedia)
    policy_config.SetDefaultEndpoint(device_id, ERole_Communications)


# ------------------------------------------------------------
# GUI
# ------------------------------------------------------------

class AudioSwitcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Output Switcher")
        self.root.geometry("575x425")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.title_label = tk.Label(
            root,
            text="Windows Audio Output Switcher",
            font=("Segoe UI", 16, "bold"),
        )
        self.title_label.pack(pady=12)

        self.device_frame = tk.Frame(root)
        self.device_frame.pack(fill="both", expand=True, padx=15)

        self.refresh_button = tk.Button(
            root,
            text="Refresh Devices",
            command=self.load_devices,
            height=2,
        )
        self.refresh_button.pack(fill="x", padx=15, pady=8)

        self.status_label = tk.Label(
            root,
            text="",
            anchor="w",
            font=("Segoe UI", 9),
        )
        self.status_label.pack(fill="x", padx=15, pady=(0, 10))

        self.load_devices()

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

        sys.exit(0)

    def clear_devices(self):
        for widget in self.device_frame.winfo_children():
            widget.destroy()

    def load_devices(self):
        self.clear_devices()

        try:
            devices = get_output_devices()
        except Exception as error:
            messagebox.showerror(
                "Error",
                f"Could not read audio devices:\n\n{error}",
            )
            self.status_label.config(text="Failed to read audio devices.")
            return

        if not devices:
            self.status_label.config(text="No active playback devices found.")
            return

        for device in devices:
            button = tk.Button(
                self.device_frame,
                text=device["name"],
                height=2,
                wraplength=520,
                command=lambda d=device: self.switch_device(d),
            )
            button.pack(fill="x", pady=5)

        self.status_label.config(
            text=f"Found {len(devices)} active playback device(s)."
        )

    def switch_device(self, device):
        try:
            set_default_audio_device(device["id"])
            self.status_label.config(
                text=f"Switched default output to: {device['name']}"
            )
        except Exception as error:
            messagebox.showerror(
                "Switch Failed",
                f"Could not switch to:\n\n{device['name']}\n\n{error}",
            )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    comtypes.CoInitialize()

    root = tk.Tk()
    app = AudioSwitcherApp(root)

    def handle_ctrl_c(signum, frame):
        app.close()

    signal.signal(signal.SIGINT, handle_ctrl_c)

    # Lets Tkinter notice Ctrl+C from the terminal.
    def poll_for_signals():
        root.after(100, poll_for_signals)

    root.after(100, poll_for_signals)
    root.mainloop()


if __name__ == "__main__":
    main()