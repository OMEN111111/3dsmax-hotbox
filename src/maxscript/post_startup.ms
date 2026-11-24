/*
 * MaxHotbox Post-Startup Bootstrap for Autodesk 3ds Max 2026 / 2027
 * 1. Registers bundle's Contents/python into sys.path
 * 2. Registers native 3ds Max main menu bar items via #cuiRegisterMenus
 * 3. Starts the MaxHotbox Python controller
 */

global gMaxHotboxRegisterMenusFn

fn gMaxHotboxRegisterMenusFn =
(
    try
    (
        local menuMgr = callbacks.notificationParam()
        if menuMgr != undefined then
        (
            local mainMenuBar = menuMgr.mainMenuBar
            if mainMenuBar != undefined then
            (
                local helpMenuId = "cee8f758-2199-411b-81e7-d3ff4a80d143"
                local subMenuId  = "8A64E19C-4B27-4E3B-9C1A-7F12D5E01A01"

                local subMenu = mainMenuBar.CreateSubMenu subMenuId "MaxHotbox" beforeId:helpMenuId
                if subMenu != undefined then
                (
                    -- 647394 is the standard MacroScript Action Table ID in 3ds Max
                    subMenu.CreateAction "8A64E19C-4B27-4E3B-9C1A-7F12D5E01A02" 647394 "MaxHotbox_Toggle`MaxHotbox" title:"启用 / 暂停热盒 (Toggle)"
                    subMenu.CreateAction "8A64E19C-4B27-4E3B-9C1A-7F12D5E01A03" 647394 "MaxHotbox_FullHotbox`MaxHotbox" title:"打开五区全局热盒 (Full Hotbox)"
                    subMenu.CreateSeparator "8A64E19C-4B27-4E3B-9C1A-7F12D5E01A04"
                    subMenu.CreateAction "8A64E19C-4B27-4E3B-9C1A-7F12D5E01A05" 647394 "MaxHotbox_Settings`MaxHotbox" title:"设置与菜单编辑器 (Settings)..."
                    subMenu.CreateAction "8A64E19C-4B27-4E3B-9C1A-7F12D5E01A06" 647394 "MaxHotbox_Rescan`MaxHotbox" title:"重新扫描挂载视口 (Rescan Viewports)"
                    subMenu.CreateAction "8A64E19C-4B27-4E3B-9C1A-7F12D5E01A07" 647394 "MaxHotbox_Reload`MaxHotbox" title:"重启热盒引擎 (Reload)"
                )
            )
        )
    )
    catch
    (
        format "[MaxHotbox] #cuiRegisterMenus warning: %\n" (getCurrentException())
    )
)

(
    local thisScript = getSourceFileName()
    local normalizedPyDir = ""
    if thisScript != undefined and thisScript != "" then
    (
        local scriptsDir = getFilenamePath thisScript
        local contentsDir = pathConfig.removePathLeaf (trimRight scriptsDir "\\/")
        local pythonDir = pathConfig.appendPath contentsDir "python"
        normalizedPyDir = substituteString pythonDir "\\" "/"
    )

    -- Register 3ds Max menu callback
    callbacks.removeScripts id:#MaxHotboxMenuCallback
    callbacks.addScript #cuiRegisterMenus gMaxHotboxRegisterMenusFn id:#MaxHotboxMenuCallback

    -- Detect running 3ds Max product year (e.g. 2026, 2027) for versioned bundle lookup
    local mv = maxVersion()
    local maxYear = if mv.count >= 8 then (mv[8] as string) else ((1998 + (mv[1] / 1000)) as string)

    -- Inject bundle python path (with fallback to ApplicationPlugins), hot-reload if already loaded, and start controller
    local pyBoot = ""
    pyBoot += "import os, sys\n"
    pyBoot += "try:\n"
    pyBoot += "    import max_hotbox as _old_mh\n"
    pyBoot += "    _old_mh.shutdown()\n"
    pyBoot += "except Exception:\n"
    pyBoot += "    pass\n"
    pyBoot += "for _k in [k for k in list(sys.modules.keys()) if k == 'max_hotbox' or k.startswith('max_hotbox.')]:\n"
    pyBoot += "    sys.modules.pop(_k, None)\n"
    pyBoot += "candidates = []\n"
    if normalizedPyDir != "" do
        pyBoot += "candidates.append(r'" + normalizedPyDir + "')\n"
    pyBoot += "for env_name in ('APPDATA', 'ProgramData'):\n"
    pyBoot += "    base = os.environ.get(env_name)\n"
    pyBoot += "    if base:\n"
    pyBoot += "        candidates.append(os.path.join(base, 'Autodesk', 'ApplicationPlugins', 'MaxHotbox_" + maxYear + ".bundle', 'Contents', 'python'))\n"
    pyBoot += "        candidates.append(os.path.join(base, 'Autodesk', 'ApplicationPlugins', 'MaxHotbox.bundle', 'Contents', 'python'))\n"
    pyBoot += "for p in candidates:\n"
    pyBoot += "    if os.path.isdir(os.path.join(p, 'max_hotbox')):\n"
    pyBoot += "        if p not in sys.path:\n"
    pyBoot += "            sys.path.insert(0, p)\n"
    pyBoot += "        break\n"
    pyBoot += "import max_hotbox\n"
    pyBoot += "max_hotbox.startup()\n"

    try
    (
        python.execute pyBoot
        format "[MaxHotbox] Initialized successfully.\n"
    )
    catch
    (
        format "[MaxHotbox] Startup failed: %\n" (getCurrentException())
    )
)
