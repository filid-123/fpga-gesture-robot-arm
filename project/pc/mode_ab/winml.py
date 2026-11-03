"""Explicit Windows ML NPU registration in an isolated Python environment."""
import asyncio


class NpuCatalog:
    def __init__(self):
        from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import initialize
        # The installed unified 2.x runtime has the 2.0 package dependency ID.
        # The preview wheel's default experimental tag does not match stable runtimes.
        self.runtime = initialize(version='2.0', min_version='2.0.0.0')
        self.runtime.__enter__()
        from winui3.microsoft.windows.ai.machinelearning import ExecutionProviderCatalog
        self.catalog = ExecutionProviderCatalog.get_default()
        self.provider = next((p for p in self.catalog.find_all_providers()
                              if p.name == 'VitisAIExecutionProvider'), None)
        if self.provider is None:
            self.close()
            raise RuntimeError('Windows ML has no AMD NPU provider; fallback refused')

    def ready(self):
        async def prepare():
            result = await self.provider.ensure_ready_async()
            return dict(state=str(result.status), diagnostic=result.diagnostic_text,
                        extended_error=str(result.extended_error))
        self.preparation = asyncio.run(prepare())
        import onnxruntime as ort
        # Python owns a distinct ORT environment. AMD's Python guidance says
        # not to call try_register(), which registers the native WinML env.
        ort.register_execution_provider_library(self.provider.name,self.provider.library_path)
        devices = [d for d in ort.get_ep_devices() if d.ep_name == 'VitisAIExecutionProvider']
        if not devices:
            # WinML registers its shared ORT. The Python wheel has a separate
            # ORT instance, so register the same certified library explicitly.
            ort.register_execution_provider_library(self.provider.name, self.provider.library_path)
            devices = [d for d in ort.get_ep_devices() if d.ep_name == self.provider.name]
        if not devices:
            raise RuntimeError('AMD NPU has no registered ONNX Runtime device; fallback refused')
        self.devices = devices
        return dict(provider=self.provider.name, library_path=self.provider.library_path,
                    preparation=self.preparation, ort_version=ort.__version__,
                    devices=[dict(name=d.ep_name, vendor=d.ep_vendor,
                                  hardware_type=str(d.device.type)) for d in devices])

    def close(self):
        if getattr(self, 'runtime', None) is not None:
            self.runtime.__exit__(None, None, None)
            self.runtime = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
