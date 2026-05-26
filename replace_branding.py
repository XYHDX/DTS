import os

files = [
    "public/index.html",
    "public/admin/index.html",
    "public/admin/login.html",
    "public/passenger/index.html",
    "public/driver/index.html",
    "public/dashboard/analytics.html"
]

def replace_in_file(path):
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        content = f.read()

    # Replace Colors (Keep variable names to avoid breaking CSS classes)
    content = content.replace("--forest-green-primary: #34d399;", "--forest-green-primary: #0F4C5C;")
    content = content.replace("--forest-green-dark: #059669;", "--forest-green-dark: #0B3945;")
    content = content.replace("--forest-green-darker: #022c22;", "--forest-green-darker: #051A20;")
    content = content.replace("--golden-wheat-light: #fef3c7;", "--golden-wheat-light: #F7E7CE;")
    content = content.replace("--golden-wheat-mid: #fbbf24;", "--golden-wheat-mid: #D4AF37;")
    content = content.replace("--golden-wheat-dark: #b45309;", "--golden-wheat-dark: #AA8C2C;")

    # Replace Fonts
    content = content.replace("IBM+Plex+Sans+Arabic:wght@300;400;500;600;700", "Tajawal:wght@300;400;500;700")
    content = content.replace("'IBM Plex Sans Arabic'", "'Tajawal'")

    # Replace Icons
    content = content.replace("🚌", "🦅⭐⭐⭐")
    content = content.replace("🚌", "🦅⭐⭐⭐") # catch any remaining

    # Let's also update the logo text in nav to reflect new brand
    content = content.replace("DamascusTransit", "SyriaTransit")
    content = content.replace("هيئة النقل في دمشق", "هيئة النقل الوطنية السورية")
    content = content.replace("نقل ذكي<br>لمدينة دمشق", "هوية جديدة<br>لمستقبل النقل في سوريا")
    content = content.replace("Smart Transit for Damascus", "Modern Transit for Syria")
    content = content.replace("Damascus Transit System", "Syrian Transit System")

    with open(path, 'w') as f:
        f.write(content)

for f in files:
    replace_in_file(f)

print("Rebranding complete")
