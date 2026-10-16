# Maintainer: Aran <aran@local>
pkgname=hp-control-center
pkgver=0.2.0
pkgrel=1
pkgdesc="Performance, power & thermal control center for HP laptops (Intel Core & Core Ultra / Arc / Iris Xe)"
arch=('any')
url="https://github.com/aran/hp-control-center"
license=('GPL-3.0-or-later')
depends=(
    'python'
    'pyside6'
    'pciutils'
    'kmod'
)
optdepends=(
    'libkscreen: display mode, refresh rate, and scale control on KDE Plasma'
    'vulkan-tools: Vulkan driver and device detection in System Info'
    'mesa-utils: OpenGL acceleration and driver detection in System Info'
)
install='hp-control-center.install'
source=()

package() {
    local _src="${startdir}"

    # 1. Install core application files into /usr/lib/hp-control-center
    install -dm755 "${pkgdir}/usr/lib/${pkgname}"
    cp -a "${_src}/core" "${pkgdir}/usr/lib/${pkgname}/"
    cp -a "${_src}/ui" "${pkgdir}/usr/lib/${pkgname}/"
    cp -a "${_src}/daemon" "${pkgdir}/usr/lib/${pkgname}/"
    cp -a "${_src}/hicolor" "${pkgdir}/usr/lib/${pkgname}/"
    install -Dm755 "${_src}/app.py" "${pkgdir}/usr/lib/${pkgname}/app.py"
    install -Dm755 "${_src}/cli.py" "${pkgdir}/usr/lib/${pkgname}/cli.py"

    # Remove any development __pycache__ artifacts from source
    find "${pkgdir}/usr/lib/${pkgname}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    # Pre-compile Python bytecode for instant application launching
    python -m compileall -q -d "/usr/lib/${pkgname}" "${pkgdir}/usr/lib/${pkgname}"
    python -O -m compileall -q -d "/usr/lib/${pkgname}" "${pkgdir}/usr/lib/${pkgname}"

    # 2. Install executable launcher wrappers in /usr/bin
    install -dm755 "${pkgdir}/usr/bin"

    # GUI launcher
    cat << 'EOF' > "${pkgdir}/usr/bin/hp-control-center"
#!/bin/sh
exec /usr/bin/python3 /usr/lib/hp-control-center/app.py "$@"
EOF
    chmod 755 "${pkgdir}/usr/bin/hp-control-center"

    # CLI tool
    cat << 'EOF' > "${pkgdir}/usr/bin/hp-control-cli"
#!/bin/sh
exec /usr/bin/python3 /usr/lib/hp-control-center/cli.py "$@"
EOF
    chmod 755 "${pkgdir}/usr/bin/hp-control-cli"
    ln -sf hp-control-cli "${pkgdir}/usr/bin/hp-control-center-cli"

    # Daemon launcher
    cat << 'EOF' > "${pkgdir}/usr/bin/hp-control-daemon"
#!/bin/sh
exec /usr/bin/python3 /usr/lib/hp-control-center/daemon/service.py "$@"
EOF
    chmod 755 "${pkgdir}/usr/bin/hp-control-daemon"

    # 3. Install systemd background service in /usr/lib/systemd/system
    install -Dm644 "${_src}/daemon/hp-control-daemon.service" \
        "${pkgdir}/usr/lib/systemd/system/hp-control-daemon.service"

    # 4. Install Desktop application entry in /usr/share/applications
    install -Dm644 "${_src}/hp-control-center.desktop" \
        "${pkgdir}/usr/share/applications/hp-control-center.desktop"

    # 5. Install application icons into /usr/share/icons/hicolor
    if [ -d "${_src}/hicolor" ]; then
        find "${_src}/hicolor" -type f | while read -r iconfile; do
            rel="${iconfile#${_src}/hicolor/}"
            install -Dm644 "$iconfile" "${pkgdir}/usr/share/icons/hicolor/${rel}"
        done
    fi
}
