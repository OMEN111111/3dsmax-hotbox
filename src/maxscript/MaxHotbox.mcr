/*
 * MaxHotbox MacroScripts for Autodesk 3ds Max 2026
 * Category: MaxHotbox
 */

macroScript MaxHotbox_Toggle
    category:"MaxHotbox"
    toolTip:"切换启用/暂停 MaxHotbox（关闭后恢复原生四元菜单）"
    buttonText:"切换热盒"
(
    on isChecked do
    (
        local state = false
        try
        (
            local mod = python.import "max_hotbox"
            state = mod.is_enabled()
        )
        catch ()
        state
    )

    on execute do
    (
        try
        (
            local mod = python.import "max_hotbox"
            mod.toggle()
        )
        catch
        (
            messageBox ("MaxHotbox 尚未初始化，请检查插件安装。\n" + (getCurrentException())) title:"MaxHotbox"
        )
    )
)

macroScript MaxHotbox_Settings
    category:"MaxHotbox"
    toolTip:"打开 MaxHotbox 设置与自定义菜单编辑器"
    buttonText:"热盒设置"
(
    on execute do
    (
        try
        (
            local mod = python.import "max_hotbox"
            mod.open_settings()
        )
        catch
        (
            messageBox ("无法打开 MaxHotbox 设置窗口:\n" + (getCurrentException())) title:"MaxHotbox"
        )
    )
)

macroScript MaxHotbox_FullHotbox
    category:"MaxHotbox"
    toolTip:"在光标处打开 Maya 风格五区全局热盒"
    buttonText:"五区热盒"
(
    on execute do
    (
        try
        (
            local mod = python.import "max_hotbox"
            mod.open_full_hotbox()
        )
        catch
        (
            messageBox ("无法打开五区热盒:\n" + (getCurrentException())) title:"MaxHotbox"
        )
    )
)

macroScript MaxHotbox_Rescan
    category:"MaxHotbox"
    toolTip:"重新扫描并挂载当前所有 3D 视口"
    buttonText:"扫描视口"
(
    on execute do
    (
        try
        (
            local mod = python.import "max_hotbox"
            local msg = mod.sync_viewports()
            pushPrompt ("MaxHotbox: " + msg)
        )
        catch
        (
            format "[MaxHotbox] Rescan failed: %\n" (getCurrentException())
        )
    )
)

macroScript MaxHotbox_Reload
    category:"MaxHotbox"
    toolTip:"安全重启 MaxHotbox 引擎"
    buttonText:"重启热盒"
(
    on execute do
    (
        try
        (
            local mod = python.import "max_hotbox"
            mod.startup()
        )
        catch
        (
            messageBox ("重启 MaxHotbox 失败:\n" + (getCurrentException())) title:"MaxHotbox"
        )
    )
)
