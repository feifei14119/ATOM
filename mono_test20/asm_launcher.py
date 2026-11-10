"""Load the actual hand-written Mono entry with HIP's module API."""
import ctypes as C
import hashlib


class AsmLauncher:
    def __init__(self, hip, binary, symbol, stream_handle):
        self.hip, self.binary, self.stream_handle = hip, bytes(binary), stream_handle
        self.module, self.function = C.c_void_p(), C.c_void_p()
        fn = hip.lib.hipModuleLaunchKernel
        fn.argtypes = [C.c_void_p, *([C.c_uint]*6), C.c_uint, C.c_void_p,
                       C.POINTER(C.c_void_p), C.POINTER(C.c_void_p)]
        fn.restype = C.c_int
        blob=C.create_string_buffer(self.binary)
        hip.call('hipModuleLoadData',C.byref(self.module),C.cast(blob,C.c_void_p))
        try:
            hip.call('hipModuleGetFunction',C.byref(self.function),self.module,symbol.encode())
        except Exception:
            self.close()
            raise

    def __call__(self,*pointers,stream):
        if len(pointers)!=15:
            raise ValueError('ASM Mono requires the 15 test10 pointer arguments')
        import torch
        if torch.cuda.current_stream().cuda_stream != self.stream_handle:
            raise RuntimeError('The test stream changed after loading ASM Mono')
        args=[C.c_uint64(p) for p in pointers]
        params=(C.c_void_p*len(args))(*[C.cast(C.pointer(x),C.c_void_p) for x in args])
        self.hip.call('hipModuleLaunchKernel',self.function,256,1,1,256,1,1,0,
                      C.c_void_p(self.stream_handle),params,None)

    def close(self):
        if self.module.value:
            self.hip.call('hipModuleUnload',self.module)
            self.module=C.c_void_p()


def binary_digest(launch):
    if isinstance(launch,AsmLauncher):
        data=launch.binary
    else:
        from mono1250.runtime.compile import _code_object
        artifacts=list(launch._mem_cache.values())
        if len(artifacts)!=1:
            raise RuntimeError('Expected exactly one compiled artifact')
        data=_code_object(artifacts[0]._ir_text)
    return hashlib.sha256(data).hexdigest()
