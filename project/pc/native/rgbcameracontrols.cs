// DirectShow capability query. Range flags come from the driver, not OpenCV guesses.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

namespace Gesture.Rgb {
    [ComImport, Guid("29840822-5B84-11D0-BD3B-00A0C911CE86"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface ICreateDevEnum {
        [PreserveSig] int CreateClassEnumerator(ref Guid category, out IEnumMoniker items, int flags);
    }
    [ComImport, Guid("55272A00-42CB-11CE-8135-00AA004BB851"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyBag {
        [PreserveSig] int Read([MarshalAs(UnmanagedType.LPWStr)] string name,
            [In, Out, MarshalAs(UnmanagedType.Struct)] ref object value, IntPtr log);
        [PreserveSig] int Write([MarshalAs(UnmanagedType.LPWStr)] string name,
            [In, MarshalAs(UnmanagedType.Struct)] ref object value);
    }
    [ComImport, Guid("C6E13370-30AC-11D0-A18C-00A0C9118956"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAMCameraControl {
        [PreserveSig] int GetRange(int property, out int minimum, out int maximum,
            out int step, out int defaultValue, out int caps);
        [PreserveSig] int Set(int property, int value, int flags);
        [PreserveSig] int Get(int property, out int value, out int flags);
    }
    [ComImport, Guid("C6E13360-30AC-11D0-A18C-00A0C9118956"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAMVideoProcAmp {
        [PreserveSig] int GetRange(int property, out int minimum, out int maximum,
            out int step, out int defaultValue, out int caps);
        [PreserveSig] int Set(int property, int value, int flags);
        [PreserveSig] int Get(int property, out int value, out int flags);
    }
    public class PropertyInfo {
        public bool Supported;
        public int RangeHResult, GetHResult;
        public int Minimum, Maximum, Step, DefaultValue, Capabilities, Value, Flags;
    }
    public class DeviceInfo {
        public int Index;
        public string FriendlyName, DevicePath, Error;
        public Dictionary<string, PropertyInfo> Controls = new Dictionary<string, PropertyInfo>();
    }
    public class ExposureWrite {
        public string DevicePath;
        public PropertyInfo Before, After;
        public int SetHResult;
        public bool ReadbackMatched;
    }
    public static class CameraControls {
        static PropertyInfo CameraProperty(IAMCameraControl control, int property) {
            PropertyInfo r = new PropertyInfo();
            r.RangeHResult = control.GetRange(property, out r.Minimum, out r.Maximum,
                out r.Step, out r.DefaultValue, out r.Capabilities);
            r.GetHResult = control.Get(property, out r.Value, out r.Flags);
            r.Supported = r.RangeHResult >= 0 && r.GetHResult >= 0 && r.Step > 0 && r.Minimum <= r.Maximum;
            return r;
        }
        static PropertyInfo VideoProperty(IAMVideoProcAmp control, int property) {
            PropertyInfo r = new PropertyInfo();
            r.RangeHResult = control.GetRange(property, out r.Minimum, out r.Maximum,
                out r.Step, out r.DefaultValue, out r.Capabilities);
            r.GetHResult = control.Get(property, out r.Value, out r.Flags);
            r.Supported = r.RangeHResult >= 0 && r.GetHResult >= 0 && r.Step > 0 && r.Minimum <= r.Maximum;
            return r;
        }
        static string BagValue(IPropertyBag bag, string key) {
            object value = null;
            return bag.Read(key, ref value, IntPtr.Zero) >= 0 && value != null ? value.ToString() : null;
        }
        static void Release(object value) {
            if (value != null && Marshal.IsComObject(value)) Marshal.ReleaseComObject(value);
        }
        // Caller owns restoration of the captured Before state in a finally block.
        // Bind by the exact device path; never write to an index that can change.
        public static ExposureWrite SetExposure(string devicePath, int value, int flags) {
            if (String.IsNullOrEmpty(devicePath) || (flags != 1 && flags != 2))
                throw new ArgumentException("Exact device path and auto=1/manual=2 flags required.");
            object source = null; IEnumMoniker enumeration = null;
            try {
                source = Activator.CreateInstance(Type.GetTypeFromCLSID(
                    new Guid("62BE5D10-60EB-11D0-BD3B-00A0C911CE86")));
                Guid category = new Guid("860BB310-5D01-11D0-BD3B-00A0C911CE86");
                int hr = ((ICreateDevEnum)source).CreateClassEnumerator(ref category, out enumeration, 0);
                if (hr == 1) throw new InvalidOperationException("No video devices.");
                Marshal.ThrowExceptionForHR(hr);
                IMoniker[] item = new IMoniker[1];
                while (enumeration.Next(1, item, IntPtr.Zero) == 0) {
                    object bagObject = null, filter = null;
                    try {
                        Guid bagGuid = typeof(IPropertyBag).GUID;
                        item[0].BindToStorage(null, null, ref bagGuid, out bagObject);
                        string path = BagValue((IPropertyBag)bagObject, "DevicePath");
                        if (!String.Equals(path, devicePath, StringComparison.OrdinalIgnoreCase)) continue;
                        Guid filterGuid = new Guid("56A86895-0AD4-11CE-B03A-0020AF0BA770");
                        item[0].BindToObject(null, null, ref filterGuid, out filter);
                        IAMCameraControl control = filter as IAMCameraControl;
                        if (control == null) throw new InvalidOperationException("No hardware exposure interface.");
                        ExposureWrite r = new ExposureWrite(); r.DevicePath = path;
                        r.Before = CameraProperty(control, 4);
                        if (!r.Before.Supported || (r.Before.Capabilities & flags) != flags ||
                            value < r.Before.Minimum || value > r.Before.Maximum ||
                            (value-r.Before.Minimum) % r.Before.Step != 0)
                            throw new ArgumentException("Exposure value/mode outside driver capabilities.");
                        r.SetHResult = control.Set(4, value, flags);
                        r.After = CameraProperty(control, 4);
                        // Mode transitions can complete asynchronously in the driver.
                        for (int attempt = 0; attempt < 8 && r.SetHResult >= 0 &&
                             (r.After.GetHResult < 0 || r.After.Flags != flags ||
                              (flags == 2 && r.After.Value != value)); attempt++) {
                            System.Threading.Thread.Sleep(50);
                            r.After = CameraProperty(control, 4);
                        }
                        // Some UVC drivers briefly reject GetRange after a mode switch
                        // while Get already reports the new value/mode correctly. The
                        // write was validated against Before's range; verify the actual
                        // readback independently, retaining both HRESULTs for auditing.
                        r.ReadbackMatched = r.SetHResult >= 0 && r.After.GetHResult >= 0 &&
                            r.After.Flags == flags && (flags == 1 || r.After.Value == value);
                        return r;
                    } finally { Release(filter); Release(bagObject); Release(item[0]); }
                }
                throw new InvalidOperationException("Selected device disconnected; no settings written.");
            } finally { Release(enumeration); Release(source); }
        }
        public static DeviceInfo[] Inspect() {
            List<DeviceInfo> records = new List<DeviceInfo>();
            object source = null;
            IEnumMoniker enumeration = null;
            try {
                source = Activator.CreateInstance(Type.GetTypeFromCLSID(
                    new Guid("62BE5D10-60EB-11D0-BD3B-00A0C911CE86")));
                Guid category = new Guid("860BB310-5D01-11D0-BD3B-00A0C911CE86");
                int hr = ((ICreateDevEnum)source).CreateClassEnumerator(ref category, out enumeration, 0);
                if (hr == 1) return records.ToArray();
                Marshal.ThrowExceptionForHR(hr);
                IMoniker[] item = new IMoniker[1];
                while (enumeration.Next(1, item, IntPtr.Zero) == 0) {
                    object bagObject = null, filter = null;
                    DeviceInfo r = new DeviceInfo(); r.Index = records.Count;
                    try {
                        Guid bagGuid = typeof(IPropertyBag).GUID;
                        item[0].BindToStorage(null, null, ref bagGuid, out bagObject);
                        IPropertyBag bag = (IPropertyBag)bagObject;
                        r.FriendlyName = BagValue(bag, "FriendlyName");
                        r.DevicePath = BagValue(bag, "DevicePath");
                        if (r.DevicePath == null) { string display; item[0].GetDisplayName(null, null, out display); r.DevicePath = display; }
                        Guid filterGuid = new Guid("56A86895-0AD4-11CE-B03A-0020AF0BA770");
                        item[0].BindToObject(null, null, ref filterGuid, out filter);
                        IAMCameraControl camera = filter as IAMCameraControl;
                        if (camera != null) {
                            r.Controls["exposure"] = CameraProperty(camera, 4);
                            r.Controls["focus"] = CameraProperty(camera, 6);
                        }
                        IAMVideoProcAmp video = filter as IAMVideoProcAmp;
                        if (video != null) {
                            r.Controls["brightness"] = VideoProperty(video, 0);
                            r.Controls["white_balance"] = VideoProperty(video, 7);
                            r.Controls["gain"] = VideoProperty(video, 9);
                        }
                    } catch (Exception ex) { r.Error = ex.GetType().Name + ": " + ex.Message; }
                    finally { Release(filter); Release(bagObject); Release(item[0]); }
                    records.Add(r);
                }
            } finally { Release(enumeration); Release(source); }
            return records.ToArray();
        }
    }
}
