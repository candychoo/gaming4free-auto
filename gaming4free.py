#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import subprocess
import requests
from seleniumbase import SB

# ================= 配置读取 =================
EMAIL        = os.environ.get("GAMING4FREE_EMAIL") or ""    # 登录邮箱
PASSWORD     = os.environ.get("GAMING4FREE_PASSWORD") or "" # 账号密码
SERVERS_ENV  = os.environ.get("SERVERS") or ""              # 服务器列表 格式: ID,名称|ID,名称
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID") or ""           # TG通知 chat id
TG_BOT_TOKEN = os.environ.get("TG_TOKEN") or ""             # TG通知 bot token

BASE_URL = "https://gaming4free.net"

# ================= Telegram 推送模块 (带图片发送) =================
def send_tg_report(status_icon, status_text, detail_msg="", screenshot_name=None):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_TOKEN 或 TG_CHAT_ID，跳过 Telegram 推送。")
        return

    # 获取北京时间 (UTC+8)
    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    # 邮箱脱敏处理
    if '@' in EMAIL:
        name, domain = EMAIL.split('@', 1)
        masked_email = f"{name[:2]}****{name[-2:]}@{domain}" if len(name) > 4 else f"{name}@{domain}"
    else:
        masked_email = "未配置/未知"

    text = (
        f"🎮 Gaming4free 续期通知\n\n"
        f"{status_icon} 状态: {status_text}\n"
        f"👤 续期账户: {masked_email}\n"
        f"📝 详情提示: {detail_msg}\n"
        f"⏱️ 执行时间: {current_time_str}"
    )

    # 如果有截图，优先通过 sendPhoto 发送
    if screenshot_name and os.path.exists(screenshot_name):
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
        try:
            with open(screenshot_name, 'rb') as photo:
                files = {'photo': photo}
                payload = {'chat_id': TG_CHAT_ID, 'caption': text}
                r = requests.post(url, data=payload, files=files, timeout=15)
                if r.status_code == 200:
                    print("📩 Telegram 状态截图及文字通知发送成功！")
                    return
        except Exception as e:
            print(f"⚠️ Telegram 发送图片异常: {e}，将降级为纯文本发送。")

    # 降级或默认的纯文本发送
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("📩 Telegram 纯文本通知发送成功！")
        else:
            print(f"⚠️ Telegram 通知发送失败: {r.text}")
    except Exception as e:
        print(f"⚠️ Telegram 通知发送异常: {e}")


# ================= Cloudflare 强力过盾增强脚本 =================
_EXPAND_JS = """
(function() {
    var ts = document.querySelector('input[name="cf-turnstile-response"]');
    if (!ts) return 'no-turnstile';
    var el = ts;
    for (var i = 0; i < 20; i++) {
        el = el.parentElement;
        if (!el) break;
        var s = window.getComputedStyle(el);
        if (s.overflow === 'hidden' || s.overflowX === 'hidden' || s.overflowY === 'hidden')
            el.style.overflow = 'visible';
        el.style.minWidth = 'max-content';
    }
    document.querySelectorAll('iframe').forEach(function(f){
        if (f.src && f.src.includes('challenges.cloudflare.com')) {
            f.style.width = '300px'; f.style.height = '65px';
            f.style.minWidth = '300px';
            f.style.visibility = 'visible'; f.style.opacity = '1';
        }
    });
    return 'done';
})()
"""

_EXISTS_JS = """
(function(){
    return document.querySelector('input[name="cf-turnstile-response"]') !== null;
})()
"""

_SOLVED_JS = """
(function(){
    var i = document.querySelector('input[name="cf-turnstile-response"]');
    return !!(i && i.value && i.value.length > 20);
})()
"""

def js_fill_input(sb, selector: str, text: str):
    safe_text = text.replace('\\', '\\\\').replace('"', '\\"')
    sb.execute_script(f"""
    (function(){{
        var el = document.querySelector('{selector}');
        if (!el) return;
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        if (nativeInputValueSetter) {{
            nativeInputValueSetter.call(el, "{safe_text}");
        }} else {{
            el.value = "{safe_text}";
        }}
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()
    """)

def handle_turnstile(sb) -> bool:
    print("🔍 检测页面是否包含 Cloudflare Turnstile 验证...")
    time.sleep(2)

    if sb.execute_script(_SOLVED_JS):
        print("✅ Cloudflare 验证已静默通过")
        return True

    for _ in range(3):
        try: sb.execute_script(_EXPAND_JS)
        except Exception: pass
        time.sleep(0.5)

    # 循环调用 SeleniumBase 核心高级图形验证破解器
    for attempt in range(6):
        if sb.execute_script(_SOLVED_JS):
            print(f"✅ Turnstile 验证成功通过（第 {attempt} 次尝试）")
            return True

        print(f"鼠标模拟追踪 -> 第 {attempt + 1} 次调用 uc_gui_click_captcha...")
        try:
            sb.uc_gui_click_captcha()
        except Exception as e:
            print(f"⚠️ uc_gui_click_captcha 触发异常: {e}")

        # 等待验证块回传结果
        for _ in range(16):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 验证成功通过（第 {attempt + 1} 次尝试）")
                return True
        print(f"⚠️ 第 {attempt + 1} 次点击未奏效，正在重试...")

    print("❌ 经过 6 次尝试后 Turnstile 验证宣告失败")
    return False


# ================= 业务自动化核心控制流 =================

def login(sb) -> bool:
    login_url = f"{BASE_URL}/login"
    print(f"🌐 正在打开登录入口: {login_url}")
    sb.uc_open_with_reconnect(login_url, reconnect_time=8)
    time.sleep(6)

    print("⏳ 等待 Cloudflare 验证以及登录表单加载...")
    cf_passed = False
    for i in range(30):
        page_src = sb.get_page_source() or ""
        if 'input[name="email"]' in page_src.lower() or 'type="email"' in page_src.lower():
            cf_passed = True
            print(f"✅ 表单节点成功捕获（耗时 {i+1} 秒）")
            break
        time.sleep(1)
        
    if not cf_passed:
        print("⚠️ 页面响应缓慢，强行使用兜底策略检测表单...")

    try:
        sb.wait_for_element('input[type="email"], input[name="email"]', timeout=15)
    except Exception:
        print("❌ 无法加载出账户登录表单，可能遭遇严格拦截")
        sb.save_screenshot("login_error_page.png")
        return False

    print("📧 自动填写登录账户...")
    email_selector = 'input[name="email"]' if sb.is_element_visible('input[name="email"]') else 'input[type="email"]'
    js_fill_input(sb, email_selector, EMAIL)
    time.sleep(0.5)
    
    print("🔑 自动填写登录密码...")
    password_selector = 'input[name="password"]' if sb.is_element_visible('input[name="password"]') else 'input[type="password"]'
    js_fill_input(sb, password_selector, PASSWORD)
    time.sleep(1)

    # 处理登录页面的 CF 人机盾
    ts_found = False
    for i in range(10):
        if sb.execute_script(_EXISTS_JS):
            ts_found = True
            print(f"🎯 侦测到存在 Turnstile 验证墙（耗时 {i+1} 秒）")
            break
        time.sleep(1)

    if ts_found:
        if not handle_turnstile(sb):
            print("❌ 登录界面的人机验证无法破解")
            sb.save_screenshot("login_captcha_failed.png")
            return False
    else:
        print("ℹ️ 页面清爽，未检测到人机拦截")

    print("🖱️ 提交登录凭证...")
    try:
        sb.press_keys(password_selector, '\n')
    except Exception:
        sb.click('button[type="submit"]')

    print("⏳ 等待控制台重定向跳转...")
    login_success = False
    for _ in range(15):
        time.sleep(1)
        cur_url = sb.get_current_url().lower()
        if "/dashboard" in cur_url or "/servers" in cur_url:
            login_success = True
            break

    if login_success:
        print(f"✅ 成功登录控制台！当前 URL: {sb.get_current_url()}")
        return True
        
    print(f"❌ 登录失败，密码可能错误或重定向超时。当前网址: {sb.get_current_url()}")
    sb.save_screenshot("login_fail_final.png")
    return False


def renew_single_server(sb, server_id, server_name):
    target_url = f"{BASE_URL}/servers/{server_id}"
    print(f"\n🖥️  正在切入服务器机房详情页 -> [{server_name}] (ID: {server_id})")
    sb.uc_open_with_reconnect(target_url, reconnect_time=8)
    time.sleep(6)

    # 检查详情页是否再次触发人机盾
    if sb.execute_script(_EXISTS_JS):
        print("🔍 详情页检测到 Turnstile 盾，启动自动解锁...")
        handle_turnstile(sb)
        time.sleep(2)

    # 截图防备，用于对比
    before_pic = f"server_{server_id}_before.png"
    sb.save_screenshot(before_pic)

    print("🔄 正在全局扫描续期控制按钮...")
    # 多重多语言选择器定位机制，防御前端面板升级导致的样式变更
    selectors = [
        'button:contains("Renew")', 'a:contains("Renew")',
        'button:contains("续期")', 'a:contains("续期")',
        'button:contains("Extend")', 'a:contains("Extend")',
        'button.btn-primary', 'button.btn-success',
        '[data-bs-target*="renew"]'
    ]

    renew_btn = None
    for sel in selectors:
        try:
            if sb.is_element_visible(sel):
                renew_btn = sb.find_element(sel, timeout=3)
                print(f"🎯 成功匹配到动作控制节点: {sel}")
                break
        except Exception:
            continue

    if not renew_btn:
        print("⚠️ 无法精准定位特定按钮，尝试使用全局模糊关键字扫描...")
        try:
            for btn in sb.find_elements("button, a"):
                text = (btn.text or "").strip().lower()
                if any(kw in text for kw in ["renew", "续期", "extend", "claim", "获得时间"]):
                    renew_btn = btn
                    print(f"🎯 模糊匹配成功: [{btn.text}]")
                    break
        except Exception:
            pass

    if not renew_btn:
        print(f"❌ 在服务器 [{server_name}] 页面未找到可执行的续期按钮，可能时间未到或已被封禁。")
        send_tg_report("⚠️", f"服务器 [{server_name}] 动作未触发", "未在页面找到任何续期按钮", before_pic)
        return

    # 平滑滚动按钮至屏幕中央并点击
    try:
        sb.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", renew_btn)
        time.sleep(1)
        renew_btn.click()
        print("🖱️ 续期请求指令已下发！等待页面缓冲反映...")
    except Exception as e:
        print(f"⚠️ 点击续期按钮发生异常: {e}，尝试强制 JS 点击")
        sb.execute_script("arguments[0].click();", renew_btn)

    time.sleep(6)

    # 再次检查是否弹出了二级模态框(Modal)或人机滑块
    if sb.execute_script(_EXISTS_JS):
        print("🔍 检测到点击按钮后弹出了 Turnstile 二级验证，正在破解...")
        handle_turnstile(sb)
        time.sleep(3)

    # 处理确认按钮（如果点击后有二次确认弹窗的话）
    try:
        for confirm_btn in sb.find_elements("button.btn-primary, button"):
            c_text = (confirm_btn.text or "").strip().lower()
            if any(kw in c_text for kw in ["confirm", "确定", "yes", "提交"]):
                confirm_btn.click()
                print("🖱️ 已自动点击二次确认弹窗按钮")
                time.sleep(4)
                break
    except Exception:
        pass

    # 最终结果盘点与快照捕获
    after_pic = f"server_{server_id}_after.png"
    sb.save_screenshot(after_pic)

    # 提取全局全局警告或提示框信息
    notice_text = "操作已安全交付，请参考附件状态图核实。"
    try:
        for alert in sb.find_elements(".alert, .notice, .toast, div[class*='alert']"):
            if alert.text:
                notice_text = alert.text.strip()
                break
    except Exception:
        pass

    print(f"📋 阶段结果审计: {notice_text}")
    send_tg_report("✅", f"服务器 [{server_name}] 续期动作已执行", notice_text, after_pic)


# ================= 调度总入口 =================
def main():
    print("#" * 35)
    print("   Gaming4free 智能续期引擎 (sing-box 架构)")
    print("#" * 35)

    if not EMAIL or not PASSWORD:
        print("❌ 核心致命错误: 环境变量 GAMING4FREE_EMAIL 或 GAMING4FREE_PASSWORD 未在 GitHub Secrets 中配置！")
        return

    # 解析多节点列表配置
    if not SERVERS_ENV:
        print("❌ 核心致命错误: 环境变量 SERVERS 未在 GitHub Secrets 中配置！")
        return
    
    server_tasks = []
    for item in SERVERS_ENV.split("|"):
        if "," in item:
            sid, sname = item.split(",", 1)
            server_tasks.append((sid.strip(), sname.strip()))
            
    if not server_tasks:
        print("❌ 绑定的服务器格式不合规，正确范例: 123456,主服务器|789012,副服务器")
        return

    # 代理网络配置接管
    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    
    sb_kwargs = {"uc": True, "headless": False}
    if IS_PROXY:
        print(f"🔗 网络管道成功并入 sing-box 本地网关: {proxy_str}")
        sb_kwargs["proxy"] = proxy_str
    else:
        print("🌐 策略调整：未启用代理，当前正处于直连裸奔状态运行")
    
    print("🚀 正在初始化云端底层浏览器沙盒...")
    with SB(**sb_kwargs) as sb:
        # 网络出口质量指纹监测
        try:
            sb.open("https://api.ip.sb/ip")
            print(f"📍 虚拟机云端当前实际出口 IP: {sb.get_text('body').strip()}")
        except Exception:
            print("⚠️ 无法获取出口 IP，但不影响后续流程，继续执行...")

        # 核心鉴权。登录一次，全线通用（共享 Cookie 会话）
        if login(sb):
            print(f"📊 分流任务启动：共计发现 {len(server_tasks)} 个待续期节点")
            for sid, sname in server_tasks:
                try:
                    renew_single_server(sb, sid, sname)
                except Exception as ex:
                    print(f"❌ 续期服务器进程 [{sname}] 遇到突发异常阻断: {ex}")
                    send_tg_report("❌", f"服务器 [{sname}] 运行发生系统级崩溃", str(ex))
        else:
            print("\n❌ 鉴权失败，全盘终止续期工作。")
            send_tg_report("❌", "总控中心拒绝登录", "账户或密码校验失败，或者未能通过全局人机验证。")

if __name__ == "__main__":
    main()
