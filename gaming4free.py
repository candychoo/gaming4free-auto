#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import requests
from seleniumbase import SB

# ================= 配置读取 =================
SERVERS_ENV  = os.environ.get("SERVERS") or ""              # 服务器列表 格式: ID,名称|ID,名称
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID") or ""           # TG通知 chat id
TG_BOT_TOKEN = os.environ.get("TG_TOKEN") or ""             # TG通知 bot token

BASE_URL = "https://gaming4free.net"

# ================= Telegram 推送模块 =================
def send_tg_report(status_icon, status_text, detail_msg="", screenshot_name=None):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_TOKEN 或 TG_CHAT_ID，跳过 Telegram 推送。")
        return

    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    text = (
        f"🎮 Gaming4free 续期通知\n\n"
        f"{status_icon} 状态: {status_text}\n"
        f"📝 详情: {detail_msg}\n"
        f"⏱️ 执行时间: {current_time_str}"
    )

    if screenshot_name and os.path.exists(screenshot_name):
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
        try:
            with open(screenshot_name, 'rb') as photo:
                r = requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': text}, files={'photo': photo}, timeout=15)
                if r.status_code == 200:
                    print("📩 Telegram 截图通知发送成功！")
                    return
        except Exception as e:
            print(f"⚠️ Telegram 发送图片异常: {e}")

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text}, timeout=10)
        print("📩 Telegram 纯文本通知发送成功！")
    except Exception:
        pass


# ================= Cloudflare 过盾增强 =================
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
    return 'done';
})()
"""

_EXISTS_JS = """
(function(){
    var frames = document.querySelectorAll('iframe');
    for (var i=0; i<frames.length; i++) {
        if (frames[i].src.includes('challenges.cloudflare.com') || frames[i].src.includes('turnstile')) return true;
    }
    return document.querySelector('input[name="cf-turnstile-response"]') !== null;
})()
"""

_SOLVED_JS = """
(function(){
    var i = document.querySelector('input[name="cf-turnstile-response"]');
    return !!(i && i.value && i.value.length > 20);
})()
"""

def handle_turnstile(sb) -> bool:
    time.sleep(2)
    if sb.execute_script(_SOLVED_JS):
        return True

    for _ in range(3):
        try: sb.execute_script(_EXPAND_JS)
        except: pass
        time.sleep(0.5)

    for attempt in range(5):
        if sb.execute_script(_SOLVED_JS):
            print(f"✅ Turnstile 验证通过！")
            return True
        print(f"🖱️ 尝试破解人机验证 (第 {attempt + 1} 次)...")
        try:
            sb.uc_gui_click_captcha()
        except:
            pass
        for _ in range(12):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 验证通过！")
                return True
    return False


# ================= 核心续期逻辑 =================
def get_remaining_time(sb):
    try:
        sb.wait_for_element_visible('#sd-timer', timeout=15)
        time.sleep(1)
        return sb.get_text('#sd-timer').strip()
    except:
        try:
            res = sb.execute_script("var el = document.querySelector('#sd-timer'); return el ? el.innerText.trim() : null;")
            return res if res else "未知"
        except:
            return "未知"

def time_to_seconds(t_str):
    try:
        h, m, s = map(int, t_str.strip().split(':'))
        return h * 3600 + m * 60 + s
    except:
        return 0

def renew_single_server(sb, server_id, server_name):
    target_url = f"{BASE_URL}/servers/{server_id}"
    print(f"\n🖥️  正在进入服务器 [{server_name}] (ID: {server_id})")
    sb.uc_open_with_reconnect(target_url, reconnect_time=8)
    time.sleep(8)

    if "login" in sb.get_current_url().lower():
        raise Exception("页面重定向到了登录页，Gaming4free 可能更改了规则或 IP 被封禁。")

    # 处理 Cookie 弹窗
    cookie_btns = ['//button[contains(., "Continue with Recommended Cookies")]', '//button[contains(., "Accept")]', '//button[contains(., "Consent")]']
    for btn in cookie_btns:
        if sb.is_element_present(btn):
            try: sb.click(btn); break
            except: pass

    t_before = get_remaining_time(sb)
    print(f"🕒 续期前剩余时间: {t_before}")
    sb.execute_script("window.scrollBy(0,800);")
    time.sleep(3)
    
    # 1. 点击触发广告按钮
    try:
        sb.wait_for_element_visible("#sd-vote-btn", timeout=10)
        sb.click('#sd-vote-btn')
        print("🖱️ 成功点击 'VOTE + ADD 90 MIN' 按钮")
    except Exception as e:
        raise Exception(f"未找到初始续期按钮: {e}")

    print("⏳ 正在观看视频广告 (等待 35 秒)...")
    time.sleep(35) 
    
    try:
        sb.execute_script("document.querySelector('#vm-submit').scrollIntoView({block: 'center'});")
        time.sleep(1)
    except:
        pass

    # 2. 检查是否有过盾验证
    if sb.execute_script(_EXISTS_JS):
        print("🛡️ 检测到 Cloudflare 盾，开始自动破解...")
        handle_turnstile(sb)
        time.sleep(2)
    else:
        print("✅ 未发现 CF 盾，当前 IP 免检。")

    # 3. 点击最终提交按钮
    try:
        sb.wait_for_element_clickable("#vm-submit", timeout=15)
        sb.click('#vm-submit')
        print("🖱️ 已点击最终确认提交按钮 'VOTE — ADDS 90 MINUTES'")
    except Exception:
        raise Exception("未能点击最终的确认提交按钮，广告可能卡住。")

    print("⏳ 等待服务器后台生效...")
    time.sleep(10)
    
    t_after = get_remaining_time(sb)
    print(f"🕒 续期后剩余时间: {t_after}")

    sec_before = time_to_seconds(t_before)
    sec_after = time_to_seconds(t_after)
    
    if sec_after > 0 and sec_before > 0:
        if sec_after <= sec_before + 120:  
            raise Exception("时间并未增加，请求可能被服务器拦截。")

    final_pic = f"success_{server_id}.png"
    sb.save_screenshot(final_pic)
    msg = f"🕒 续期前: {t_before}\n🎉 续期后: {t_after}"
    send_tg_report("✅", f"[{server_name}] 续期成功", msg, final_pic)


# ================= 主程序入口 =================
def main():
    print("#" * 35)
    print("   Gaming4free 免登录续期 (sing-box)")
    print("#" * 35)

    if not SERVERS_ENV:
        print("❌ 致命错误: 环境变量 SERVERS 未配置！")
        return
    
    server_tasks = []
    for item in SERVERS_ENV.split("|"):
        if "," in item:
            sid, sname = item.split(",", 1)
            server_tasks.append((sid.strip(), sname.strip()))
            
    if not server_tasks:
        print("❌ 服务器格式错误，正确范例: 123456,主服务器|789012,副服务器")
        return

    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    
    sb_kwargs = {"uc": True, "headless": False}
    if IS_PROXY:
        print(f"🔗 挂载 sing-box 代理网关: {proxy_str}")
        sb_kwargs["proxy"] = proxy_str
    
    print("🚀 启动底座浏览器...")
    with SB(**sb_kwargs) as sb:
        try:
            sb.open("https://api.ip.sb/ip")
            print(f"📍 当前云端出口 IP: {sb.get_text('body').strip()}")
        except:
            pass

        for sid, sname in server_tasks:
            try:
                renew_single_server(sb, sid, sname)
            except Exception as ex:
                err_pic = f"error_{sid}.png"
                try: sb.save_screenshot(err_pic)
                except: pass
                print(f"❌ [{sname}] 执行失败: {ex}")
                send_tg_report("❌", f"[{sname}] 执行异常", str(ex), err_pic)

if __name__ == "__main__":
    main()
