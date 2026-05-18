import aiosqlite
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.database import get_db
from app.config import settings
from app.models.operations import get_all_playlists, get_all_tracks, update_track_title, delete_playlist


router = APIRouter()

COOKIE_NAME = "audio_dashboard_session"


def is_authenticated(request: Request) -> bool:
    if not settings.dashboard_password:
        return True
    return request.cookies.get(COOKIE_NAME) == settings.dashboard_password


@router.get("/dashboard/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/dashboard", status_code=303)

    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio Cache - Dashboard Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --accent-color: #a855f7;
            --accent-hover: #c084fc;
            --glass-bg: rgba(17, 24, 39, 0.7);
            --glass-border: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 80% 20%, rgba(168, 85, 247, 0.15), transparent 40%),
                              radial-gradient(circle at 20% 80%, rgba(59, 130, 246, 0.15), transparent 40%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-card {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            animation: fadeIn 0.6s ease-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .logo-wrap {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo-wrap h1 {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(to right, #a855f7, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        .logo-wrap p {
            color: var(--text-muted);
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 24px;
        }
        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: #d1d5db;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .form-input {
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            padding: 14px 18px;
            color: var(--text-main);
            font-size: 15px;
            font-family: inherit;
            outline: none;
            transition: all 0.3s;
        }
        .form-input:focus {
            background: rgba(255, 255, 255, 0.08);
            border-color: var(--accent-color);
            box-shadow: 0 0 0 4px rgba(168, 85, 247, 0.15);
        }
        .btn {
            width: 100%;
            background: linear-gradient(to right, var(--accent-color), #8b5cf6);
            border: none;
            border-radius: 12px;
            padding: 14px;
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 10px 20px rgba(168, 85, 247, 0.25);
        }
        .btn:hover {
            transform: translateY(-2px);
            background: linear-gradient(to right, var(--accent-hover), #9d4edd);
            box-shadow: 0 12px 24px rgba(168, 85, 247, 0.35);
        }
        .error-msg {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 12px;
            padding: 12px;
            color: #ef4444;
            font-size: 14px;
            text-align: center;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo-wrap">
            <h1>Audio Cache</h1>
            <p>Admin Dashboard Control Panel</p>
        </div>
        <form method="POST" action="/dashboard/login">
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" class="form-input" placeholder="••••••••" required autofocus>
            </div>
            <button type="submit" class="btn">Sign In</button>
        </form>
    </div>
</body>
</html>"""
    return HTMLResponse(html)


@router.post("/dashboard/login", response_class=HTMLResponse)
async def login_post(password: str = Form(...)):
    if password == settings.dashboard_password:
        res = RedirectResponse(url="/dashboard", status_code=303)
        res.set_cookie(COOKIE_NAME, password, httponly=True)
        return res

    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio Cache - Dashboard Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --accent-color: #a855f7;
            --accent-hover: #c084fc;
            --glass-bg: rgba(17, 24, 39, 0.7);
            --glass-border: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 80% 20%, rgba(168, 85, 247, 0.15), transparent 40%),
                              radial-gradient(circle at 20% 80%, rgba(59, 130, 246, 0.15), transparent 40%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-card {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            animation: fadeIn 0.6s ease-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .logo-wrap {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo-wrap h1 {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(to right, #a855f7, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        .logo-wrap p {
            color: var(--text-muted);
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 24px;
        }
        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: #d1d5db;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .form-input {
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            padding: 14px 18px;
            color: var(--text-main);
            font-size: 15px;
            font-family: inherit;
            outline: none;
            transition: all 0.3s;
        }
        .form-input:focus {
            background: rgba(255, 255, 255, 0.08);
            border-color: var(--accent-color);
            box-shadow: 0 0 0 4px rgba(168, 85, 247, 0.15);
        }
        .btn {
            width: 100%;
            background: linear-gradient(to right, var(--accent-color), #8b5cf6);
            border: none;
            border-radius: 12px;
            padding: 14px;
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 10px 20px rgba(168, 85, 247, 0.25);
        }
        .btn:hover {
            transform: translateY(-2px);
            background: linear-gradient(to right, var(--accent-hover), #9d4edd);
            box-shadow: 0 12px 24px rgba(168, 85, 247, 0.35);
        }
        .error-msg {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 12px;
            padding: 12px;
            color: #ef4444;
            font-size: 14px;
            text-align: center;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo-wrap">
            <h1>Audio Cache</h1>
            <p>Admin Dashboard Control Panel</p>
        </div>
        <div class="error-msg">Invalid password. Please try again.</div>
        <form method="POST" action="/dashboard/login">
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" class="form-input" placeholder="••••••••" required autofocus>
            </div>
            <button type="submit" class="btn">Sign In</button>
        </form>
    </div>
</body>
</html>"""
    return HTMLResponse(html)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_get(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    if not is_authenticated(request):
        return RedirectResponse(url="/dashboard/login", status_code=303)

    playlists = await get_all_playlists(db)
    tracks = await get_all_tracks(db)

    # Compute Statistics
    playlists_count = len(playlists)
    tracks_count = len(tracks)
    complete_count = sum(1 for t in tracks if t.status == "complete")
    processing_count = sum(1 for t in tracks if t.status in ["pending", "processing"])
    error_count = sum(1 for t in tracks if t.status == "error")

    # Group tracks by playlist_id for display
    playlist_tracks = {}
    for t in tracks:
        playlist_tracks.setdefault(t.playlist_id, []).append(t)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio Cache - Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --accent-color: #a855f7;
            --accent-hover: #c084fc;
            --glass-bg: rgba(17, 24, 39, 0.7);
            --glass-border: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 90% 10%, rgba(168, 85, 247, 0.12), transparent 50%),
                              radial-gradient(circle at 10% 90%, rgba(59, 130, 246, 0.12), transparent 50%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
        }}
        .header-brand h1 {{
            font-size: 32px;
            font-weight: 800;
            background: linear-gradient(to right, #a855f7, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-brand p {{
            color: var(--text-muted);
            font-size: 14px;
            margin-top: 4px;
        }}
        .btn-logout {{
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 12px;
            padding: 10px 20px;
            color: #ef4444;
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.3s;
        }}
        .btn-logout:hover {{
            background: rgba(239, 68, 68, 0.2);
            transform: translateY(-2px);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: var(--glass-bg);
            backdrop-filter: blur(8px);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .stat-card .label {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .stat-card .value {{
            font-size: 36px;
            font-weight: 800;
            color: var(--text-main);
        }}
        .stat-card.accent {{ border-color: rgba(168, 85, 247, 0.3); }}
        .stat-card.complete {{ border-color: rgba(34, 197, 94, 0.3); }}
        .stat-card.processing {{ border-color: rgba(234, 179, 8, 0.3); }}
        .stat-card.error {{ border-color: rgba(239, 68, 68, 0.3); }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 24px;
            border-left: 4px solid var(--accent-color);
            padding-left: 12px;
        }}

        .playlist-card {{
            background: var(--glass-bg);
            backdrop-filter: blur(8px);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }}
        details[open] summary svg {{
            transform: rotate(180deg);
        }}

        .playlist-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--glass-border);
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}
        .playlist-title h3 {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .playlist-title p {{
            font-size: 13px;
            color: var(--text-muted);
        }}
        .playlist-badge {{
            background: rgba(168, 85, 247, 0.1);
            border: 1px solid rgba(168, 85, 247, 0.3);
            color: var(--accent-color);
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 8px;
            text-transform: uppercase;
        }}

        .tracks-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }}
        .tracks-table th {{
            color: var(--text-muted);
            font-weight: 600;
            padding: 12px 8px;
            border-bottom: 1px solid var(--glass-border);
            font-size: 13px;
            text-transform: uppercase;
        }}
        .tracks-table td {{
            padding: 14px 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            color: var(--text-main);
        }}
        .tracks-table tr:hover {{
            background: rgba(255, 255, 255, 0.02);
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            display: inline-block;
        }}
        .badge.complete {{ background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3); color: #4ade80; }}
        .badge.pending, .badge.processing {{ background: rgba(234, 179, 8, 0.1); border: 1px solid rgba(234, 179, 8, 0.3); color: #facc15; }}
        .badge.error {{ background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; }}

        .edit-form {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .edit-input {{
            flex: 1;
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            padding: 6px 12px;
            color: var(--text-main);
            font-size: 14px;
            outline: none;
            transition: all 0.3s;
        }}
        .edit-input:focus {{
            border-color: var(--accent-color);
            background: rgba(255,255,255,0.06);
        }}
        .btn-save {{
            background: rgba(168, 85, 247, 0.15);
            border: 1px solid rgba(168, 85, 247, 0.3);
            border-radius: 8px;
            padding: 6px 12px;
            color: var(--accent-color);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .btn-save:hover {{
            background: rgba(168, 85, 247, 0.25);
            transform: translateY(-1px);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-brand">
                <h1>Dashboard</h1>
                <p>Track cache management & system performance</p>
            </div>
            <a href="/dashboard/logout" class="btn-logout">Sign Out</a>
        </header>

        <div class="stats-grid">
            <div class="stat-card accent">
                <span class="label">Playlists</span>
                <span class="value">{playlists_count}</span>
            </div>
            <div class="stat-card accent">
                <span class="label">Total Tracks</span>
                <span class="value">{tracks_count}</span>
            </div>
            <div class="stat-card complete">
                <span class="label">Completed</span>
                <span class="value">{complete_count}</span>
            </div>
            <div class="stat-card processing">
                <span class="label">Processing</span>
                <span class="value">{processing_count}</span>
            </div>
            <div class="stat-card error">
                <span class="label">Errors</span>
                <span class="value">{error_count}</span>
            </div>
        </div>

        <h2 class="section-title">Playlists Overview</h2>
"""

    if not playlists:
        html += '<p style="color: var(--text-muted); text-align: center; margin-top: 20px;">No playlists found yet.</p>'
    else:
        for p in playlists:
            tr_html = ""
            for t in playlist_tracks.get(p.id, []):
                tr_html += f"""
                <tr>
                    <td style="width: 40px;">{t.position}</td>
                    <td>
                        <form method="POST" action="/dashboard/track/{t.id}/title" class="edit-form">
                            <input type="text" name="title" value="{t.title or ''}" class="edit-input" required>
                            <button type="submit" class="btn-save">Save</button>
                        </form>
                    </td>
                    <td style="width: 140px;"><span class="badge {t.status}">{t.status}</span></td>
                    <td style="width: 80px;">{t.duration or 'N/A'}s</td>
                </tr>
                """

            html += f"""
            <div class="playlist-card" style="padding: 16px 28px;">

                <details>
                    <summary style="cursor: pointer; list-style: none; display: flex; justify-content: space-between; align-items: center; outline: none;">
                        <div class="playlist-title">
                            <h3 style="display: inline-flex; align-items: center; gap: 8px;">
                                {p.id}
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="transition: transform 0.2s;"><path d="m6 9 6 6 6-6"/></svg>
                            </h3>
                            <div style="margin-top: 4px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                                <a href="{p.url}" target="_blank" onclick="event.stopPropagation();" style="color: var(--accent-hover); text-decoration: none;">View on YouTube &rarr;</a>
                                <span style="color: var(--text-muted);">- Click anywhere to toggle {len(playlist_tracks.get(p.id, []))} tracks</span>
                            </div>
                        </div>
                        <div>
                            <span class="playlist-badge">{p.status}</span>
                        </div>
                    </summary>

                    <div style="border-top: 1px solid var(--glass-border); padding-top: 20px; margin-top: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                            <h4 style="font-size: 14px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;">Playlist Tracks</h4>
                            <a href="/dashboard/playlist/{p.id}/delete" onclick="return confirm('Are you sure you want to delete this playlist and all its tracks?');" style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 6px 14px; color: #ef4444; font-size: 13px; font-weight: 600; text-decoration: none; cursor: pointer; transition: all 0.3s;">Delete Playlist</a>
                        </div>
                        <table class="tracks-table">
                            <thead>
                                <tr>
                                    <th>Pos</th>
                                    <th>Title</th>
                                    <th>Status</th>
                                    <th>Duration</th>
                                </tr>
                            </thead>
                            <tbody>
                                {tr_html or '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No tracks in playlist</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </details>
            </div>
            """

    html += """
    </div>
</body>
</html>"""
    return HTMLResponse(html)


@router.post("/dashboard/track/{track_id}/title", response_class=RedirectResponse)
async def track_title_post(request: Request, track_id: str, title: str = Form(...), db: aiosqlite.Connection = Depends(get_db)):
    if not is_authenticated(request):
        return RedirectResponse(url="/dashboard/login", status_code=303)

    await update_track_title(db, track_id, title)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard/playlist/{playlist_id}/delete", response_class=RedirectResponse)
async def playlist_delete_get(request: Request, playlist_id: str, db: aiosqlite.Connection = Depends(get_db)):
    if not is_authenticated(request):
        return RedirectResponse(url="/dashboard/login", status_code=303)

    await delete_playlist(db, playlist_id)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard/logout", response_class=RedirectResponse)
async def logout_get():
    res = RedirectResponse(url="/dashboard/login", status_code=303)
    res.delete_cookie(COOKIE_NAME)
    return res


