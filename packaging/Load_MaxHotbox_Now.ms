/*
 * MaxHotbox Immediate Live Loader for Autodesk 3ds Max 2026
 * Run via: 3ds Max -> Scripting -> Run Script... (脚本 -> 运行脚本...)
 * Or drag-and-drop this .ms file directly into a 3ds Max 2026 viewport.
 */

(
    try
    (
        local thisDir = getFilenamePath (getSourceFileName())
        local candidates = #(
            (pathConfig.appendPath thisDir "MaxHotbox.bundle"),
            (pathConfig.appendPath (systemTools.getEnvVariable "APPDATA") "Autodesk\\ApplicationPlugins\\MaxHotbox.bundle"),
            (pathConfig.appendPath (systemTools.getEnvVariable "ProgramData") "Autodesk\\ApplicationPlugins\\MaxHotbox.bundle")
        )

        local foundBundle = undefined
        for c in candidates do
        (
            if (doesFileExist (pathConfig.appendPath c "Contents\\scripts\\post_startup.ms")) do
            (
                foundBundle = c
                exit
            )
        )

        if foundBundle == undefined then
        (
            messageBox "未找到 MaxHotbox.bundle，请先运行 install.bat 安装插件。" title:"MaxHotbox 启动失败"
        )
        else
        (
            local mcrPath = pathConfig.appendPath foundBundle "Contents\\macroscripts\\MaxHotbox.mcr"
            local bootPath = pathConfig.appendPath foundBundle "Contents\\scripts\\post_startup.ms"
            if (doesFileExist mcrPath) do fileIn mcrPath
            fileIn bootPath

            local statusMsg = ""
            try
            (
                local mh = python.import "max_hotbox"
                statusMsg = mh.sync_viewports()
            )
            catch ()

            messageBox (
                "MaxHotbox 已在当前 3ds Max 2026 会话中立即启动！\n\n" +
                "加载来源:\n" + foundBundle + "\n\n" +
                "运行状态: " + statusMsg + "\n\n" +
                "操作提示:\n" +
                "• 在任意 3D 视口按住 右键 / Shift+右键 / Ctrl+右键 / Alt+右键 并划动鼠标\n" +
                "• 按住 ` (反引号键) 呼出五区全局热盒\n" +
                "• 按 Esc 或松开在中心区域取消"
            ) title:"MaxHotbox 已激活"
        )
    )
    catch
    (
        format "[MaxHotbox] Live load error: %\n" (getCurrentException())
        messageBox ("启动 MaxHotbox 失败:\n" + (getCurrentException())) title:"MaxHotbox 错误"
    )
)
