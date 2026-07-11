#!/bin/bash

# install.sh
# ─────────────────────────────────────────────────────────────────────────────
# Script for installing 3xui-shop (giakhoavu640-prog Fork)
# ─────────────────────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# НАСТРОЙКИ РЕПОЗИТОРИЯ
REPO_OWNER="giakhoavu640-prog"
REPO_NAME="3xui-shop"
VERSION_FILE=".version"
TMP_DIR="/tmp/3xui-shop_update"
BACKUP_DIR="/tmp/3xui-shop_backup"
TRANSLATIONS_DIR="app/locales"

QUIET=false

# Обычный лог для простых строк
log() {
    if [ "$QUIET" = false ]; then
        echo -e "$@"
    fi
}

# КРИТИЧЕСКИЙ ИСПРАВЛЕННЫЙ ЛОГ: отправляет текст в stderr, 
# чтобы функции-генераторы строк не забивали переменные мусором
log_err() {
    if [ "$QUIET" = false ]; then
        echo -e "$@" >&2
    fi
}

find_project_root() {
    local current_dir="$1"
    local check_dir="$current_dir"
    
    while [[ "$check_dir" != "/" ]]; do
        if [[ -f "$check_dir/$VERSION_FILE" ]]; then
            echo "$check_dir"
            return 0
        fi
        check_dir="$(dirname "$check_dir")"
    done
    
    if [[ -d "$current_dir/$REPO_NAME" ]] && [[ -f "$current_dir/$REPO_NAME/$VERSION_FILE" ]]; then
        echo "$current_dir/$REPO_NAME"
        return 0
    fi
    
    echo ""
}

PROJECT_ROOT=$(find_project_root "$(pwd)")
if [[ -n "$PROJECT_ROOT" ]]; then
    PROJECT_DIR="$PROJECT_ROOT"
else
    PROJECT_DIR="$(pwd)"
    [[ "$(basename "$PROJECT_DIR")" != "$REPO_NAME" ]] && PROJECT_DIR="$PROJECT_DIR/$REPO_NAME"
fi

install_dependencies() {
    local packages="curl tar gettext"
    local OS="unknown"
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    elif [ -f /etc/debian_version ]; then
        OS="debian"
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
    fi
    
    log "🖥️ Detected OS: $OS"
    log "📦 Installing packages..."
    
    case $OS in
        ubuntu|debian|armbian)
            sudo apt-get update -qq >/dev/null 2>&1
            sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $packages >/dev/null 2>&1
            ;;
        centos|almalinux|rocky|ol|rhel)
            sudo yum -y update -q >/dev/null 2>&1
            sudo yum install -y -q $packages >/dev/null 2>&1
            ;;
        fedora|amzn|virtuozzo)
            sudo dnf -y update -q >/dev/null 2>&1
            sudo dnf install -y -q $packages >/dev/null 2>&1
            ;;
        arch|manjaro|parch)
            sudo pacman -Syu --noconfirm --quiet >/dev/null 2>&1
            sudo pacman -S --noconfirm --quiet $packages >/dev/null 2>&1
            ;;
        opensuse-tumbleweed|opensuse|suse)
            sudo zypper -q refresh >/dev/null 2>&1
            sudo zypper install -y -q $packages >/dev/null 2>&1
            ;;
        *)
            log "⚠️ Unknown OS, trying apt as fallback..."
            sudo apt-get update -qq >/dev/null 2>&1
            sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $packages >/dev/null 2>&1
            ;;
    esac

    log "✅ All dependencies are installed."
}

check_dependencies() {
    log "🔍 Checking dependencies..."
    install_dependencies
    
    for dep in curl tar gettext; do
        if ! command -v "$dep" &>/dev/null; then
            echo "❌ Failed to install: $dep" >&2
            echo "💡 Please install the required packages manually" >&2
            exit 1
        fi
    done
}

get_current_version() {
    local version_path="$PROJECT_DIR/$VERSION_FILE"
    [[ -f "$version_path" ]] && cat "$version_path" || echo "none"
}

get_latest_version() {
    local response
    local version
    
    set +e
    response=$(curl -sL "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/latest")
    version=$(echo "$response" | grep -oP '"tag_name": "\K(.*)(?=")')
    set -e

    if [[ -z "$version" ]]; then
        echo "main"
    else
        echo "$version"
    fi
}

download_and_extract_release() {
    local version="$1"
    local url
    
    if [[ "$version" == "main" ]]; then
        url="https://github.com/$REPO_OWNER/$REPO_NAME/archive/refs/heads/main.tar.gz"
    else
        url="https://github.com/$REPO_OWNER/$REPO_NAME/archive/refs/tags/${version}.tar.gz"
    fi

    # Используем log_err, чтобы вывод не перехватывался в переменную
    log_err "⬇️ Downloading source: $url"
    rm -rf "$TMP_DIR"
    mkdir -p "$TMP_DIR"
    
    curl -sSL "$url" -o "$TMP_DIR/release.tar.gz"

    log_err "📦 Extracting files..."
    tar -xzf "$TMP_DIR/release.tar.gz" -C "$TMP_DIR" --strip-components=1

    # Вот это ЕДИНСТВЕННОЕ, что должно уйти в stdout функции
    echo "$TMP_DIR"
}

install_new_version() {
    local extracted_dir="$1"
    
    log "🔄 Replacing project files..."
    if [ ! -d "$extracted_dir" ]; then
        echo "❌ Error: Source directory does not exist: $extracted_dir" >&2
        exit 1
    fi
    mkdir -p "$PROJECT_DIR"
    cp -r "$extracted_dir/." "$PROJECT_DIR/"
    log "✅ Project files replaced."
}

backup_translations() {
    if [[ -d "$PROJECT_DIR/$TRANSLATIONS_DIR" ]]; then
        log "💾 Backing up translations..."
        rm -rf "$BACKUP_DIR/$TRANSLATIONS_DIR"
        mkdir -p "$BACKUP_DIR/$TRANSLATIONS_DIR"
        
        for lang_dir in "$PROJECT_DIR/$TRANSLATIONS_DIR"/*/; do
            [ -d "$lang_dir" ] || continue
            local lang_name
            lang_name=$(basename "$lang_dir")
            if [ "$lang_name" != "backup" ]; then
                cp -r "$lang_dir" "$BACKUP_DIR/$TRANSLATIONS_DIR/"
            fi
        done
        
        log "✅ Translations backed up."
    fi
}

cleanup() {
    log "🧹 Cleaning up..."
    rm -rf "$TMP_DIR"
    rm -f "$PROJECT_DIR/release.tar.gz"
    log "✅ Cleanup complete."
}

main() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -q|--quiet)
                QUIET=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    check_dependencies

    local is_update=false
    if [[ -n "$PROJECT_ROOT" ]]; then
        log "🔄 Updating existing installation in: $PROJECT_DIR"
        is_update=true
    else
        log "📦 Installing new copy in: $PROJECT_DIR"
    fi

    local current_version
    current_version=$(get_current_version)
    log "🔍 Current version: $current_version"

    local latest_version
    latest_version=$(get_latest_version)
    log "🌟 Latest version: $latest_version"

    if [[ "$current_version" == "$latest_version" && "$latest_version" != "main" ]]; then
        log "✅ Project is already up-to-date ($current_version)"
        exit 0
    fi

    if [[ "$is_update" == "true" ]]; then
        backup_translations
    fi

    local extracted_dir
    extracted_dir=$(download_and_extract_release "$latest_version")
    install_new_version "$extracted_dir"

    if [[ "$is_update" == "true" ]] && [[ -d "$BACKUP_DIR/$TRANSLATIONS_DIR" ]]; then
        log "🔤 Merging translations from backup..."
        rm -rf "$PROJECT_DIR/$TRANSLATIONS_DIR/backup"
        mkdir -p "$PROJECT_DIR/$TRANSLATIONS_DIR/backup"
        
        cp -r "$BACKUP_DIR/$TRANSLATIONS_DIR"/* "$PROJECT_DIR/$TRANSLATIONS_DIR/backup/"
        
        cd "$PROJECT_DIR"
        if [ -f "./scripts/manage_translations.sh" ]; then
            bash "./scripts/manage_translations.sh" --merge
        fi
    fi

    echo "$latest_version" > "$PROJECT_DIR/$VERSION_FILE"
    cleanup

    if [[ "$is_update" == "true" ]]; then
        log "🎉 Update completed! Project version: $current_version → $latest_version"
    else
        log "🎉 Installation completed! Project version: $latest_version"
    fi
}

main "$@"
