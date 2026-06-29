import flet as ft
import json, os, uuid, shutil, traceback, re, csv, zipfile
from datetime import datetime

LOG_FILE = "/storage/emulated/0/Documents/vzor_error_log.txt"

def log_error(msg):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()}: {msg}\n")
    except:
        pass

log_error("===== APP IMPORT START =====")

try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
    log_error("fpdf imported")
except ImportError:
    PDF_AVAILABLE = False
    log_error("fpdf NOT imported")

SETTINGS_FILE = "settings.json"
RECORDS_FILE = "records.json"
REPORTS_DIR = "reports"
BACKUP_DIR = "backups"

TYPE_FREQ_PRESETS = {
    "FPV": ("5800.0", "2400.0"),
    "DJI": ("5700.0", "2400.0"),
    "Yaga": ("5200.0", "2400.0"),
    "Krylo": ("5800.0", "915.0"),
    "Radar": ("0", "0"),
    "Radar udarny": ("0", "0"),
    "Perehvatchik": ("0", "0"),
}

def validate_frequency(v):
    res = bool(re.fullmatch(r"\d+(\.\d+)?", v))
    log_error(f"validate_frequency({v}) -> {res}")
    return res

def validate_date(v):
    try:
        datetime.strptime(v, "%Y-%m-%d")
        log_error(f"validate_date({v}) -> True")
        return True
    except:
        log_error(f"validate_date({v}) -> False")
        return False

def validate_time(v):
    try:
        datetime.strptime(v, "%H:%M")
        log_error(f"validate_time({v}) -> True")
        return True
    except:
        log_error(f"validate_time({v}) -> False")
        return False

def load_json(path, default=None):
    if default is None: default = {}
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                log_error(f"load_json({path}) -> {len(data)} keys")
                return data
    except Exception as e:
        log_error(f"load_json({path}) ERROR: {e}")
    log_error(f"load_json({path}) -> default")
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log_error(f"save_json({path}) ok")
    except Exception as e:
        log_error(f"save_json({path}) ERROR: {e}")

load_records = lambda: load_json(RECORDS_FILE, [])
save_records = lambda r: save_json(RECORDS_FILE, r)

def add_record(data):
    log_error("add_record called")
    records = load_records()
    rec = {"id": str(uuid.uuid4()), "date": data["date"], "time": data["time"],
           "direction": data["direction"], "point": data["point"], "type": data["type"],
           "freq_video": data["freq_video"], "freq_control": data["freq_control"],
           "suppressed": bool(data["suppressed"]), "exported": False}
    records.append(rec)
    save_records(records)
    log_error(f"add_record done, id={rec['id']}")
    return rec

def update_record(rid, new_data):
    log_error(f"update_record {rid}")
    records = load_records()
    for r in records:
        if r["id"] == rid:
            r.update(new_data)
            break
    save_records(records)

def delete_record(rid):
    log_error(f"delete_record {rid}")
    records = [r for r in load_records() if r["id"] != rid]
    save_records(records)

def get_filtered_records(filters):
    log_error(f"get_filtered_records {filters}")
    records = load_records()
    if not filters:
        return records
    res = []
    for r in records:
        ok = True
        if filters.get("date_from") and r["date"] < filters["date_from"]: ok = False
        if filters.get("date_to") and r["date"] > filters["date_to"]: ok = False
        if filters.get("type") and r["type"] != filters["type"]: ok = False
        if filters.get("direction") and r["direction"] != filters["direction"]: ok = False
        if filters.get("suppressed") is not None and r["suppressed"] != filters["suppressed"]: ok = False
        if ok: res.append(r)
    log_error(f"get_filtered_records -> {len(res)} records")
    return res

def export_csv(records, path):
    log_error(f"export_csv to {path}")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Date","Time","Direction","Point","Type","Freq_video","Freq_control","Suppressed"])
        for r in records:
            w.writerow([r["date"], r["time"], r["direction"], r["point"], r["type"],
                        r["freq_video"], r["freq_control"], "Yes" if r["suppressed"] else "No"])
    log_error("export_csv done")

def export_pdf(records, path):
    log_error(f"export_pdf to {path}")
    if not PDF_AVAILABLE:
        log_error("export_pdf: fpdf missing")
        raise RuntimeError("fpdf missing")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, "Vzor Report", ln=True, align='C')
    pdf.ln(5)
    cols = [("Date",25),("Time",15),("Direction",30),("Point",25),("Type",20),("Freq v",25),("Freq c",25),("Suppr",20)]
    for h,w in cols:
        pdf.cell(w,7,h,border=1)
    pdf.ln()
    for r in records:
        pdf.cell(25,6,r["date"],border=1)
        pdf.cell(15,6,r["time"],border=1)
        pdf.cell(30,6,r["direction"],border=1)
        pdf.cell(25,6,r["point"],border=1)
        pdf.cell(20,6,r["type"],border=1)
        pdf.cell(25,6,r["freq_video"],border=1)
        pdf.cell(25,6,r["freq_control"],border=1)
        pdf.cell(20,6,"Yes" if r["suppressed"] else "No",border=1)
        pdf.ln()
    pdf.output(path)
    log_error("export_pdf done")

def create_backup():
    log_error("create_backup called")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    path = os.path.join(BACKUP_DIR, name)
    with zipfile.ZipFile(path, 'w') as zf:
        for f in [RECORDS_FILE, SETTINGS_FILE, LOG_FILE]:
            if os.path.exists(f):
                zf.write(f)
                log_error(f"backup added {f}")
    log_error(f"backup created: {path}")
    return path

def restore_backup(zip_path):
    log_error(f"restore_backup {zip_path}")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall()
    log_error("restore_backup done")
    return True

def main(page: ft.Page):
    log_error(">>> main() started")
    try:
        page.title = "Vzor"
        page.padding = 10
        page.scroll = ft.ScrollMode.AUTO
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        log_error("page props set")

        settings = load_json(SETTINGS_FILE, {})
        is_dark = settings.get("dark_mode", False)
        page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
        log_error(f"theme_mode={'dark' if is_dark else 'light'}")

        dirs = ["Dnepryany","Tarasovka","Podokalinozka","Mayachka"]
        points = ["Nartsys","Pion","Landysh","Gladiolus","Khrizantema"]
        types = list(TYPE_FREQ_PRESETS.keys())
        log_error("dropdown data ready")

        def dd(label, hint, opts, val, expand=True):
            return ft.Dropdown(
                label=label, hint_text=hint,
                options=[ft.dropdown.Option(o) for o in opts],
                value=val, expand=expand
            )

        dir_dd = dd("Direction","Select direction",dirs,settings.get("direction"))
        point_dd = dd("Point","Select point",points,settings.get("point"))
        dark_sw = ft.Switch(label="Dark mode", value=is_dark)

        def save_settings(e):
            log_error("save_settings called")
            settings["direction"] = dir_dd.value
            settings["point"] = point_dd.value
            settings["dark_mode"] = dark_sw.value
            save_json(SETTINGS_FILE, settings)
            page.theme_mode = ft.ThemeMode.DARK if dark_sw.value else ft.ThemeMode.LIGHT
            page.snack_bar = ft.SnackBar(ft.Text("Settings saved"), bgcolor=ft.Colors.GREEN)
            page.snack_bar.open = True
            page.update()
            page.go("/")

        def settings_view():
            log_error("settings_view built")
            return ft.View("/settings", [
                ft.AppBar(title=ft.Text("Settings"), bgcolor=ft.Colors.PRIMARY),
                ft.Column([dir_dd, point_dd, dark_sw,
                           ft.ElevatedButton("Save", on_click=save_settings)],
                          spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
            ])

        def home_view():
            log_error(">>> home_view building")
            search_type = dd("Type filter","All",["All"]+types,"All",False)
            search_dir = dd("Dir filter","All",["All"]+dirs,"All",False)
            date_from = ft.TextField(label="From (YYYY-MM-DD)", width=160)
            date_to = ft.TextField(label="To (YYYY-MM-DD)", width=160)
            suppr = ft.Dropdown(label="Suppressed", options=[ft.dropdown.Option("All"),
                                ft.dropdown.Option("Yes"),ft.dropdown.Option("No")], value="All", width=120)
            PAGE_SIZE = 20
            offset = 0

            type_dd = dd("Type","Select type",types,None)
            fv = ft.TextField(label="Freq video (MHz)", expand=True)
            fc = ft.TextField(label="Freq control (MHz)", expand=True)
            date_f = ft.TextField(label="Date", value=datetime.now().strftime("%Y-%m-%d"), expand=True)
            time_f = ft.TextField(label="Time", value=datetime.now().strftime("%H:%M"), expand=True)
            supp_sw = ft.Switch(label="Suppressed", value=False)
            rec_list = ft.ListView(expand=True, spacing=5)

            log_error("home_view widgets created")

            def on_type_change(e):
                if type_dd.value in TYPE_FREQ_PRESETS:
                    fv.value, fc.value = TYPE_FREQ_PRESETS[type_dd.value]
                    page.update()
                    log_error(f"on_type_change {type_dd.value} -> presets set")
            type_dd.on_change = on_type_change

            tmpl_dd = ft.Dropdown(label="Load template", options=[], width=160)
            tmpl_name = ft.TextField(label="Template name", width=150)

            def refresh_templates():
                log_error("refresh_templates")
                tmpl_dd.options = [ft.dropdown.Option(n) for n in settings.get("templates",{}).keys()]
                page.update()

            refresh_templates()

            def apply_tmpl(name):
                log_error(f"apply_tmpl {name}")
                t = settings.get("templates",{}).get(name)
                if t:
                    type_dd.value = t.get("type")
                    fv.value = t.get("freq_video","")
                    fc.value = t.get("freq_control","")
                    supp_sw.value = t.get("suppressed",False)
                    page.update()
            tmpl_dd.on_change = lambda e: apply_tmpl(e.control.value) if e.control.value else None

            def save_tmpl(e):
                log_error("save_tmpl")
                name = tmpl_name.value.strip()
                if not name:
                    page.snack_bar = ft.SnackBar(ft.Text("Enter name"))
                    page.snack_bar.open = True
                    page.update()
                    return
                settings.setdefault("templates",{})[name] = {
                    "type": type_dd.value, "freq_video": fv.value,
                    "freq_control": fc.value, "suppressed": supp_sw.value
                }
                save_json(SETTINGS_FILE, settings)
                refresh_templates()
                page.snack_bar = ft.SnackBar(ft.Text(f"Template '{name}' saved"), bgcolor=ft.Colors.GREEN)
                page.snack_bar.open = True
                page.update()

            def get_filters():
                f = {}
                if search_type.value != "All": f["type"] = search_type.value
                if search_dir.value != "All": f["direction"] = search_dir.value
                if date_from.value: f["date_from"] = date_from.value
                if date_to.value: f["date_to"] = date_to.value
                if suppr.value == "Yes": f["suppressed"] = True
                elif suppr.value == "No": f["suppressed"] = False
                log_error(f"get_filters -> {f}")
                return f

            def load_page(off=0, clear=True):
                nonlocal offset
                log_error(f"load_page off={off} clear={clear}")
                if clear:
                    rec_list.controls.clear()
                    offset = 0
                filters = get_filters()
                all_recs = get_filtered_records(filters)
                all_recs.sort(key=lambda r: r["date"]+r["time"], reverse=True)
                batch = all_recs[off:off+PAGE_SIZE]
                log_error(f"load_page batch size {len(batch)}")
                for rec in batch:
                    icon = "🔄" if not rec.get("exported") else "✅"
                    supp_text = "Suppressed" if rec["suppressed"] else "Active"
                    label = f"{rec['date']} {rec['time']} | {rec['type']} | V:{rec['freq_video']} C:{rec['freq_control']} | {supp_text}"
                    edit_btn = ft.IconButton(ft.icons.EDIT, on_click=lambda e, rid=rec["id"]: edit_dialog(rid))
                    del_btn = ft.IconButton(ft.icons.DELETE, on_click=lambda e, rid=rec["id"]: delete_and_refresh(rid))
                    rec_list.controls.append(
                        ft.Row([
                            ft.Container(ft.Text(f"{icon} {label}", size=14, expand=True),
                                         padding=8, bgcolor=ft.Colors.BLUE_GREY_50, border_radius=8, expand=True),
                            edit_btn, del_btn
                        ])
                    )
                if len(all_recs) > off+PAGE_SIZE:
                    rec_list.controls.append(
                        ft.ElevatedButton("Load more", on_click=lambda e: load_page(offset=off+PAGE_SIZE, clear=False))
                    )
                page.update()
                log_error("load_page done")

            def delete_and_refresh(rid):
                log_error(f"delete_and_refresh {rid}")
                delete_record(rid)
                load_page()

            def edit_dialog(rid):
                log_error(f"edit_dialog {rid}")
                rec = next((r for r in load_records() if r["id"]==rid), None)
                if not rec:
                    log_error(f"edit_dialog: record {rid} not found")
                    return
                e_type = dd("Type","",types,rec["type"])
                e_fv = ft.TextField(label="Freq video", value=rec["freq_video"])
                e_fc = ft.TextField(label="Freq control", value=rec["freq_control"])
                e_date = ft.TextField(label="Date", value=rec["date"])
                e_time = ft.TextField(label="Time", value=rec["time"])
                e_sup = ft.Switch(label="Suppressed", value=rec["suppressed"])

                def save_edit(e):
                    log_error("save_edit dialog")
                    new = {"type": e_type.value, "freq_video": e_fv.value,
                           "freq_control": e_fc.value, "date": e_date.value,
                           "time": e_time.value, "suppressed": e_sup.value}
                    update_record(rid, new)
                    dlg.open = False
                    load_page()
                    page.update()

                def close_dlg(d):
                    d.open = False
                    page.update()

                dlg = ft.AlertDialog(title=ft.Text("Edit record"),
                    content=ft.Column([e_type,e_fv,e_fc,e_date,e_time,e_sup], spacing=10, width=300),
                    actions=[ft.TextButton("Save", on_click=save_edit),
                             ft.TextButton("Cancel", on_click=lambda e: close_dlg(dlg))])
                page.dialog = dlg
                dlg.open = True
                page.update()

            def on_save(e):
                log_error("on_save clicked")
                settings = load_json(SETTINGS_FILE, {})
                if not settings.get("direction") or not settings.get("point"):
                    page.snack_bar = ft.SnackBar(ft.Text("Set direction/point in settings"))
                    page.snack_bar.open = True; page.update(); return
                if not type_dd.value:
                    page.snack_bar = ft.SnackBar(ft.Text("Select type!"))
                    page.snack_bar.open = True; page.update(); return
                if not fv.value or not fc.value:
                    page.snack_bar = ft.SnackBar(ft.Text("Fill frequencies!"))
                    page.snack_bar.open = True; page.update(); return
                if not validate_frequency(fv.value) or not validate_frequency(fc.value):
                    page.snack_bar = ft.SnackBar(ft.Text("Invalid frequency"))
                    page.snack_bar.open = True; page.update(); return
                if not validate_date(date_f.value) or not validate_time(time_f.value):
                    page.snack_bar = ft.SnackBar(ft.Text("Invalid date/time"))
                    page.snack_bar.open = True; page.update(); return
                data = {"date": date_f.value, "time": time_f.value, "direction": settings["direction"],
                        "point": settings["point"], "type": type_dd.value,
                        "freq_video": fv.value, "freq_control": fc.value, "suppressed": supp_sw.value}
                add_record(data)
                load_page()
                fv.value = ""; fc.value = ""; supp_sw.value = False
                date_f.value = datetime.now().strftime("%Y-%m-%d")
                time_f.value = datetime.now().strftime("%H:%M")
                page.snack_bar = ft.SnackBar(ft.Text("Record saved"), bgcolor=ft.Colors.GREEN)
                page.snack_bar.open = True
                page.update()

            def export_view(fmt):
                log_error(f"export_view {fmt}")
                records = get_filtered_records(get_filters())
                if not records:
                    page.snack_bar = ft.SnackBar(ft.Text("No records"))
                    page.snack_bar.open = True; page.update(); return
                os.makedirs(REPORTS_DIR, exist_ok=True)
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                if fmt=="csv":
                    path = os.path.join(REPORTS_DIR, f"export_{ts}.csv")
                    export_csv(records, path)
                elif fmt=="pdf":
                    if not PDF_AVAILABLE:
                        page.snack_bar = ft.SnackBar(ft.Text("Install fpdf2"))
                        page.snack_bar.open = True; page.update(); return
                    path = os.path.join(REPORTS_DIR, f"export_{ts}.pdf")
                    export_pdf(records, path)
                page.snack_bar = ft.SnackBar(ft.Text(f"Exported to {path}"), bgcolor=ft.Colors.GREEN)
                page.snack_bar.open = True; page.update()

            def do_backup(e):
                log_error("do_backup")
                path = create_backup()
                page.snack_bar = ft.SnackBar(ft.Text(f"Backup: {path}"))
                page.snack_bar.open = True; page.update()

            def do_restore(e):
                log_error("do_restore")
                fp = ft.FilePicker(on_result=lambda r: restore_and_refresh(r) if r.files else None)
                page.overlay.append(fp)
                fp.pick_files(allowed_extensions=["zip"])

            def restore_and_refresh(e):
                log_error("restore_and_refresh")
                if e.files:
                    restore_backup(e.files[0].path)
                    load_page()
                    page.snack_bar = ft.SnackBar(ft.Text("Restored"))
                    page.snack_bar.open = True; page.update()

            def share_log(e):
                log_error("share_log")
                if os.path.exists(LOG_FILE):
                    tmp = f"share_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    shutil.copy(LOG_FILE, tmp)
                    page.launch_url(f"file://{os.path.abspath(tmp)}")
                    page.snack_bar = ft.SnackBar(ft.Text("Log shared"))
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("No log"))
                page.snack_bar.open = True; page.update()

            log_error("home_view return View")
            return ft.View("/", [
                ft.AppBar(title=ft.Text("Vzor"), actions=[
                    ft.IconButton(ft.icons.SETTINGS, on_click=lambda e: page.go("/settings")),
                    ft.IconButton(ft.icons.SHARE, on_click=share_log)
                ]),
                ft.Column([
                    ft.Text("Filters", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row([search_type, search_dir, date_from, date_to, suppr], wrap=True, spacing=5),
                    ft.ElevatedButton("Apply filters", on_click=lambda e: load_page()),
                    ft.Divider(),
                    ft.Text("Records", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.ElevatedButton("CSV", on_click=lambda e: export_view("csv"), icon=ft.icons.TABLE_CHART),
                        ft.ElevatedButton("PDF", on_click=lambda e: export_view("pdf"), icon=ft.icons.PICTURE_AS_PDF),
                        ft.ElevatedButton("Backup", on_click=do_backup, icon=ft.icons.BACKUP),
                        ft.ElevatedButton("Restore", on_click=do_restore, icon=ft.icons.RESTORE),
                    ], spacing=5),
                    ft.Container(content=rec_list, height=300),
                    ft.Divider(),
                    ft.Text("New record", size=16, weight=ft.FontWeight.BOLD),
                    type_dd,
                    ft.Row([fv, fc], spacing=5),
                    ft.Row([date_f, time_f], spacing=5),
                    supp_sw,
                    ft.ElevatedButton("Save", on_click=on_save, icon=ft.icons.SAVE, expand=True),
                    ft.Text("Templates", size=14, weight=ft.FontWeight.BOLD),
                    ft.Row([tmpl_dd, tmpl_name, ft.ElevatedButton("Save template", on_click=save_tmpl)], spacing=5),
                ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
            ])

        def stats_view():
            log_error("stats_view")
            records = load_records()
            total = len(records)
            supp = sum(1 for r in records if r["suppressed"])
            by_type = {}
            by_dir = {}
            for r in records:
                by_type[r["type"]] = by_type.get(r["type"],0)+1
                by_dir[r["direction"]] = by_dir.get(r["direction"],0)+1
            type_chart = ft.PieChart(
                sections=[ft.PieChartSection(value=c, title=f"{t} ({c})",
                    color=ft.Colors.primaries[i%len(ft.Colors.primaries)]) for i,(t,c) in enumerate(by_type.items())],
                expand=True)
            dir_chart = ft.PieChart(
                sections=[ft.PieChartSection(value=c, title=f"{d} ({c})",
                    color=ft.Colors.primaries[i%len(ft.Colors.primaries)]) for i,(d,c) in enumerate(by_dir.items())],
                expand=True)
            return ft.View("/stats", [
                ft.AppBar(title=ft.Text("Statistics"), bgcolor=ft.Colors.PRIMARY,
                          actions=[ft.IconButton(ft.icons.HOME, on_click=lambda e: page.go("/"))]),
                ft.Column([
                    ft.Text(f"Total: {total} | Suppressed: {supp}", size=16),
                    ft.Text("By type", size=14, weight=ft.FontWeight.BOLD), type_chart,
                    ft.Text("By direction", size=14, weight=ft.FontWeight.BOLD), dir_chart,
                ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
            ])

        def route_change(route):
            log_error(f"route_change to {route}")
            page.views.clear()
            if route == "/settings":
                page.views.append(settings_view())
            elif route == "/stats":
                page.views.append(stats_view())
            else:
                page.views.append(home_view())
            page.update()

        page.on_route_change = route_change
        log_error("Calling route_change initially")
        route_change(page.route)   # <-- ИСПРАВЛЕНИЕ: явно строим начальную страницу
        log_error("initial route_change completed")

    except Exception as e:
        log_error(f"!!! MAIN EXCEPTION: {traceback.format_exc()}")
        page.controls.clear()
        page.add(ft.Text(f"Critical error:\n{traceback.format_exc()}", color=ft.Colors.RED))
        page.update()

if __name__ == "__main__":
    log_error("Before ft.app(target=main)")
    try:
        ft.app(target=main)
        log_error("After ft.app (should not be printed)")
    except Exception as e:
        log_error(f"ft.app failed: {traceback.format_exc()}")
