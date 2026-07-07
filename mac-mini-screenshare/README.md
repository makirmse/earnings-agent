# Screen share to your Mac Mini from Windows (over Tailscale)

Goal: sit at your **Windows PC anywhere**, click one icon, and see your **Mac Mini's
screen at home** — so you can open its files, folders, and apps like you're sitting
in front of it. No more typing in the terminal.

You already have Tailscale on the Mac Mini, so you're most of the way there.

> **Which method should I use?**
> - **See and control the whole Mac** (open apps, click around) → use **Screen Sharing** below. This is what you asked for.
> - **Just grab a document quickly** → the **Bonus** section at the bottom shows how to make the Mac's files appear as a normal drive in Windows Explorer. Even easier for pulling files.
>
> You can set up both. They don't conflict.

---

## What you need first (both computers)

1. **Tailscale on the Mac Mini** — you have this. ✅
2. **Tailscale on the Windows PC** — install it and **sign in with the same account**
   as the Mac Mini. Download: <https://tailscale.com/download/windows>
   - Both machines must be signed in to the *same* Tailscale account. That's what
     lets them talk to each other privately from anywhere.
3. **A VNC viewer app on Windows** — this is the "window" that shows the Mac's screen.
   Free and easy: **RealVNC Viewer** → <https://www.realvnc.com/en/connect/download/viewer/>
   (TigerVNC or UltraVNC also work if you prefer.)

That's it. Everything below is a one-time setup, then a 2-click routine.

---

## One-time setup (do this once)

### Step 1 — Turn on Screen Sharing on the Mac Mini

**The easy automated way:** on the Mac Mini, open **Terminal**, then run:

```bash
cd ~/projects/earnings-agent/mac-mini-screenshare   # adjust path if yours differs
bash setup-mac-mini.sh
```

Type your Mac password if it asks. The script turns on Screen Sharing and then
**prints the exact address** to type on Windows. Write that address down.

**The manual way (if you prefer clicking, or the script says it couldn't confirm):**

- Open **System Settings** → **General** → **Sharing**
- Turn **ON** the **Screen Sharing** switch
- Click the **(i)** info button next to Screen Sharing. If you see
  **"VNC viewers may control screen with password"**, turn it on and set a short
  password. (This makes Windows VNC apps connect most reliably. Remember this password.)

> On older macOS it's **System Preferences → Sharing → Screen Sharing**, then
> **Computer Settings… → "VNC viewers may control screen with password."**

### Step 2 — Get the Mac Mini's Tailscale address

The setup script prints it. If you need it again later, run on the Mac Mini:

```bash
bash whats-my-address.sh
```

It looks like `100.x.y.z` (a Tailscale IP), for example `100.101.102.103`.
This address is **stable** — it stays the same, so you only need it once.

### Step 3 — Save the connection on Windows (so it becomes one click)

1. Open **RealVNC Viewer** on the Windows PC.
2. In the address bar at the top, type the Mac Mini's address from Step 2
   (e.g. `100.101.102.103`) and press **Enter**.
3. It will ask you to sign in:
   - If you set a **VNC password** in Step 1, enter that.
   - Otherwise enter your **Mac Mini login username and password**.
4. Check **"Remember password"** so you don't retype it.
5. RealVNC will save this as a tile/shortcut. **Right-click it → Rename** to
   something like **"Mac Mini"**. You can also right-click → **Create desktop shortcut**.

Done. From now on it's just two clicks.

---

## Connecting any time after that

1. Make sure **Tailscale is running** on the Windows PC (green icon in the taskbar).
2. **Double-click your "Mac Mini" tile** in RealVNC Viewer.

You'll see the Mac Mini's desktop. Open Finder, grab your documents, drag files —
whatever you'd do sitting in front of it.

> **To move a file from the Mac to Windows during a screen-share session:** the
> simplest reliable way is to email it to yourself, drop it in iCloud/Dropbox/Google
> Drive, or use the Bonus file-drive method below. Plain VNC screen sharing shows the
> screen but doesn't always do drag-and-drop file copy between the two computers.

---

## If something doesn't work

- **"Can't connect" / it just spins**
  - Is Tailscale **connected on BOTH** computers right now? Open the Tailscale app on
    each and confirm it says connected. On Windows the taskbar icon should be solid.
  - On the Mac Mini, run `bash whats-my-address.sh` again and double-check you typed
    the address correctly on Windows.
  - Is the Mac Mini awake? If it's asleep it can't answer. See the sleep tip below.

- **It connects but asks for a password you don't know**
  - Use your **Mac Mini account login** (the name/password you use to unlock the Mac),
    or the **VNC password** you set in Step 1. If unsure, redo Step 1's info-button
    part and set a fresh VNC password.

- **Address didn't print / "Tailscale not found"**
  - Open the **Tailscale app** on the Mac Mini once and make sure it's **logged in and
    connected**, then re-run the script.

- **Keep the Mac Mini awake so you can always reach it**
  - **System Settings → Displays → Advanced** (or **Energy Saver**) →
    turn on **"Prevent automatic sleeping when the display is off"** (wording varies by
    macOS). A Mac Mini with no monitor is happy to stay awake. This ensures it's always
    reachable when you're away.

---

## Bonus: the easiest way to just *pull a document*

If you mostly want to **grab files** (not control the whole Mac), turn the Mac Mini's
folders into a normal **drive letter in Windows Explorer**:

**On the Mac Mini (one time):**
- **System Settings → General → Sharing** → turn **ON** **File Sharing**
- Click the **(i)** next to File Sharing → note which folders are shared (add your
  documents folder if needed) and make sure your user is allowed.

**On the Windows PC:**
1. Open **File Explorer**.
2. In the address bar at the top, type:
   `\\100.x.y.z`  (the Mac Mini's Tailscale address, with two backslashes in front)
   and press **Enter**.
3. Enter your **Mac Mini username and password** when asked; check **Remember**.
4. Your Mac's shared folders appear like any Windows folder — drag files across.
5. To make it permanent: right-click the shared folder → **"Map network drive…"** →
   pick a letter (e.g. `Z:`) → check **"Reconnect at sign-in."** Now it's always
   there as drive **Z:** in "This PC."

This is often the friendliest option when the goal is simply *"get that document off
the Mac Mini."*

---

## Files in this folder

| File | What it does | Where to run it |
|------|--------------|-----------------|
| `README.md` | This guide | — |
| `setup-mac-mini.sh` | Turns on Screen Sharing and prints your address | On the **Mac Mini** |
| `whats-my-address.sh` | Reminds you of the Mac Mini's address | On the **Mac Mini** |

Nothing here touches your Windows PC or does anything destructive — the scripts only
turn on Apple's built-in Screen Sharing and read your Tailscale address.
