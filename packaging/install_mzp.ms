/*
 * MaxHotbox Drag-and-Drop (.mzp) Installer for Autodesk 3ds Max 2026 / 2027
 * Detects the running 3ds Max product year (2026 / 2027), installs an isolated
 * per-version bundle (%APPDATA%\Autodesk\ApplicationPlugins\MaxHotbox_<year>.bundle),
 * safely migrates any legacy MaxHotbox.bundle, and activates immediately.
 */

(
    try
    (
        local thisFile = getSourceFileName()
        local setupRoot = getFilenamePath thisFile
        local normalizedRoot = substituteString setupRoot "\\" "/"

        local mv = maxVersion()
        local maxYear = if mv.count >= 8 then (mv[8] as integer) else (1998 + (mv[1] / 1000))
        local maxYearStr = maxYear as string

        local pyInstall = ""
        pyInstall += "import os, shutil, xml.etree.ElementTree as ET\n"
        pyInstall += "setup_root = r'" + normalizedRoot + "'\n"
        pyInstall += "year = '" + maxYearStr + "'\n"
        pyInstall += "src_bundle = os.path.join(setup_root, 'MaxHotbox.bundle')\n"
        pyInstall += "if not os.path.isdir(src_bundle):\n"
        pyInstall += "    raise FileNotFoundError('Missing MaxHotbox.bundle in: ' + setup_root)\n"
        pyInstall += "appdata = os.environ.get('APPDATA')\n"
        pyInstall += "if not appdata:\n"
        pyInstall += "    raise RuntimeError('APPDATA environment variable is not set')\n"
        pyInstall += "plugins_dir = os.path.join(appdata, 'Autodesk', 'ApplicationPlugins')\n"
        pyInstall += "os.makedirs(plugins_dir, exist_ok=True)\n"
        pyInstall += "def _patch_xml(bundle_dir, yr):\n"
        pyInstall += "    xp = os.path.join(bundle_dir, 'PackageContents.xml')\n"
        pyInstall += "    tree = ET.parse(xp)\n"
        pyInstall += "    root = tree.getroot()\n"
        pyInstall += "    root.set('ProductCode', '{9D4C8A12-' + yr + '-4B7E-9A51-5E8C3A4F1000}')\n"
        pyInstall += "    root.set('Description', 'Maya-style multi-level radial marking menu and 5-zone hotbox plugin for Autodesk 3ds Max ' + yr + '.')\n"
        pyInstall += "    for req in root.findall('.//RuntimeRequirements'):\n"
        pyInstall += "        req.set('SeriesMin', yr)\n"
        pyInstall += "        req.set('SeriesMax', yr)\n"
        pyInstall += "    tree.write(xp, encoding='utf-8', xml_declaration=True)\n"
        pyInstall += "try:\n"
        pyInstall += "    import max_hotbox\n"
        pyInstall += "    max_hotbox.shutdown()\n"
        pyInstall += "except Exception:\n"
        pyInstall += "    pass\n"
        pyInstall += "legacy_bundle = os.path.join(plugins_dir, 'MaxHotbox.bundle')\n"
        pyInstall += "if os.path.isdir(legacy_bundle):\n"
        pyInstall += "    try:\n"
        pyInstall += "        ltree = ET.parse(os.path.join(legacy_bundle, 'PackageContents.xml'))\n"
        pyInstall += "        mins = [int(r.attrib.get('SeriesMin', '2026')[:4]) for r in ltree.findall('.//RuntimeRequirements')]\n"
        pyInstall += "        maxs = [int(r.attrib.get('SeriesMax', '2026')[:4]) for r in ltree.findall('.//RuntimeRequirements')]\n"
        pyInstall += "        y_int = int(year)\n"
        pyInstall += "        if mins and maxs and min(mins) <= y_int <= max(maxs):\n"
        pyInstall += "            for other in (2026, 2027):\n"
        pyInstall += "                if other != y_int and min(mins) <= other <= max(maxs):\n"
        pyInstall += "                    ob = os.path.join(plugins_dir, f'MaxHotbox_{other}.bundle')\n"
        pyInstall += "                    if not os.path.exists(ob):\n"
        pyInstall += "                        shutil.copytree(legacy_bundle, ob)\n"
        pyInstall += "                        _patch_xml(ob, str(other))\n"
        pyInstall += "            shutil.rmtree(legacy_bundle)\n"
        pyInstall += "    except Exception:\n"
        pyInstall += "        pass\n"
        pyInstall += "dst_bundle = os.path.join(plugins_dir, f'MaxHotbox_{year}.bundle')\n"
        pyInstall += "if os.path.exists(dst_bundle):\n"
        pyInstall += "    shutil.rmtree(dst_bundle)\n"
        pyInstall += "shutil.copytree(src_bundle, dst_bundle)\n"
        pyInstall += "_patch_xml(dst_bundle, year)\n"
        pyInstall += "import builtins\n"
        pyInstall += "builtins._max_hotbox_installed_bundle = dst_bundle\n"

        python.execute pyInstall

        local dstBundle = ""
        try
        (
            local bmod = python.import "builtins"
            dstBundle = bmod._max_hotbox_installed_bundle
        )
        catch ()

        if dstBundle != "" then
        (
            local mcrPath = pathConfig.appendPath dstBundle "Contents\\macroscripts\\MaxHotbox.mcr"
            local bootPath = pathConfig.appendPath dstBundle "Contents\\scripts\\post_startup.ms"
            if (doesFileExist mcrPath) do fileIn mcrPath
            if (doesFileExist bootPath) do fileIn bootPath

            local statusMsg = ""
            try
            (
                local mh = python.import "max_hotbox"
                statusMsg = mh.sync_viewports()
            )
            catch ()

            messageBox (
                "MaxHotbox v0.1.5 (3ds Max " + maxYearStr + ") 安装并启动成功！\n\n" +
                "安装目录:\n" + dstBundle + "\n\n" +
                "当前运行状态: " + statusMsg + "\n\n" +
                "使用指南（在任意 3D 视口内）:\n" +
                "• 按住 右键 / Shift+右键 / Ctrl+右键 / Alt+右键 / 空格+右键 -> 划动选择 -> 松开执行\n" +
                "• 带 ▸ 标记的按钮悬停展开二级菜单；悬停下方 [‹ 返回上级] 或轻点左键返回上级\n" +
                "• 带 □ 方块的按钮：划到主按钮=快捷/视口拖动，划到右侧 □ =打开参数/石墨数值面板\n" +
                "• 顶部菜单栏 [MaxHotbox] 专属按钮可随时打开配置面板并一键切回原生四元菜单！"
            ) title:"MaxHotbox 安装成功"
        )
        else
        (
            messageBox "MaxHotbox 安装路径获取失败，请打开 MAXScript 侦听器 (F11) 查看日志。" title:"MaxHotbox 安装提示"
        )
    )
    catch
    (
        format "[MaxHotbox] MZP install error: %\n" (getCurrentException())
        messageBox ("MaxHotbox 安装失败:\n" + (getCurrentException())) title:"MaxHotbox 安装失败"
    )
)
