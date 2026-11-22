/*
 * MaxHotbox Runtime Unload Helper for Autodesk 3ds Max 2026
 * Safely stops the active controller and removes registered UI callbacks.
 */

(
    try
    (
        python.execute "import max_hotbox; max_hotbox.shutdown()"
    )
    catch ()

    try
    (
        callbacks.removeScripts id:#MaxHotboxMenuCallback
        callbacks.removeScripts id:#MaxHotboxLifecycleCallbacks
    )
    catch ()

    pushPrompt "MaxHotbox 已安全停止并恢复 3ds Max 原生四元菜单。"
    format "[MaxHotbox] Unloaded from current 3ds Max session.\n"
)
