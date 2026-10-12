#if !defined(__OHOS__)
#error "This probe must be compiled for HarmonyOS/OpenHarmony."
#endif

__attribute__((visibility("default")))
int ohos_gsas_toolchain_probe(void)
{
    return 22;
}
