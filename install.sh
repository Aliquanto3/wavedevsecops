#!/bin/sh
# Installeur de WaveDevSecOps pour macOS et Linux, sans droits administrateur (AD-15, AD-20).
#
# Commande unique (voir le README) :
#   curl -fsSL https://raw.githubusercontent.com/Aliquanto3/wavedevsecops/main/install.sh | sh
#
# curl respecte HTTPS_PROXY (et NO_PROXY) : le script, l'installeur de uv, pixi, git et les
# archives passent tous par le proxy posé. Aucun sudo : tout est écrit dans le profil de
# l'utilisateur. Relancé, il met l'application à jour et conserve progress.json.
# POSIX sh uniquement (testé avec dash) ; tout le code est dans main(), appelée en dernière
# ligne : un téléchargement tronqué n'exécute rien.
#
# Réglages (variables d'environnement, toutes facultatives) :
#   WDS_DATA_DIR        dossier des données (défaut : comme l'application, voir get_data_dir)
#   WDS_INSTALL_METHOD  clone (défaut) ou zip (archive tar.gz de GitHub, sans git)
#   WDS_INSTALL_REF     branche ou étiquette à installer (défaut main)
#   HTTPS_PROXY         proxy d'entreprise ; pose aussi UV_SYSTEM_CERTS=true
#   UV_INSTALL_DIR      dossier de uv (défaut ~/.local/bin)
#   WDS_INSTALL_FORCE_PROVISION_GIT=1  ignore le git du poste (CI : exerce la voie pixi)
# Réglages de test (aucun accès réseau, aucune installation réelle) :
#   WDS_INSTALL_SIMULATE=1, WDS_INSTALL_SIMULATE_GIT=<version|none>, WDS_INSTALL_SIMULATE_GIT_PATH=<chemin>,
#   WDS_INSTALL_SIMULATE_UV=<version|none>, WDS_INSTALL_SIMULATE_OS=<Darwin|Linux>,
#   WDS_INSTALL_SIMULATE_ARCH=<uname -m>, WDS_INSTALL_SIMULATE_XCODE=<ok|missing>,
#   WDS_INSTALL_SIMULATE_TOOLS_TOML=<fichier>,
#   WDS_INSTALL_SIMULATE_FAIL=<étapes séparées par des virgules : download, pixi, clone, sync, checksum>,
#   WDS_INSTALL_LIBONLY=1 (définit les fonctions sans rien lancer).

INSTALLER_VERSION=1
REPO_URL='https://github.com/Aliquanto3/wavedevsecops.git'
ARCHIVE_URL_BASE='https://github.com/Aliquanto3/wavedevsecops/archive'
RAW_URL_BASE='https://raw.githubusercontent.com/Aliquanto3/wavedevsecops'
SIMULATE=0
[ "${WDS_INSTALL_SIMULATE:-}" = 1 ] && SIMULATE=1
CURRENT_STEP=''
PROXY=''
SIMLOG=''

NETWORK_SETTINGS="HTTPS_PROXY (par exemple http://proxy.entreprise:8080) ; NO_PROXY=127.0.0.1,localhost ; UV_SYSTEM_CERTS=true (certificats de l'entreprise)"
ROUTE_TEXT="par clone (WDS_INSTALL_METHOD=clone, il faut git) ou par archive (export WDS_INSTALL_METHOD=zip), sans git. À défaut, téléchargez l'archive de l'application depuis GitHub, décompressez-la dans le dossier « app » du dossier de données, puis lancez « uv sync » dedans."

# --- Messages -----------------------------------------------------------------------------

step() {
    CURRENT_STEP=$1
    printf '\n==> %s\n' "$1"
}

info() { printf '    %s\n' "$1"; }

# fail <cause> [<variables à régler>] [<voie de repli>] : à n'appeler que hors de $( ).
fail() {
    {
        printf '\n'
        printf "L'installation s'est arrêtée à l'étape « %s ».\n" "$CURRENT_STEP"
        printf 'Cause : %s\n' "$1"
        [ -n "${2:-}" ] && printf 'Variables à régler : %s\n' "$2"
        [ -n "${3:-}" ] && printf 'Voie de repli : %s\n' "$3"
        printf "Relancez la même commande : l'installeur reprend là où il s'est arrêté et ne casse rien.\n"
    } >&2
    exit 1
}

# --- Fonctions pures (testées) ------------------------------------------------------------

trim() { printf '%s' "$1" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'; }

# Les composantes numériques de tête : « v2.43.0 (Apple Git-154) » donne 2.43.0.
version_core() {
    printf '%s' "$1" | sed -n 's/^[[:space:]]*v\{0,1\}\([0-9][0-9]*\(\.[0-9][0-9]*\)*\).*/\1/p'
}

# version_at_least <version> <minimum> : code 0 si version >= minimum.
version_at_least() {
    _va=$(version_core "$1")
    _vb=$(version_core "$2")
    [ -n "$_va" ] || return 1
    awk -v a="$_va" -v b="$_vb" 'BEGIN {
        n = split(a, x, "."); m = split(b, y, ".")
        if (m > n) n = m
        for (i = 1; i <= n; i++) {
            p = x[i] + 0; q = y[i] + 0
            if (p != q) exit (p > q ? 0 : 1)
        }
        exit 0
    }'
}

# tool_value <id> <clé> [<sous-table>] : valeur texte de tools.toml, lue sur $REGISTRY.
# Mini-lecteur (pas de parseur TOML en sh) : « [[tool]] », « [tool.<nom>] », valeurs entre guillemets.
tool_value() {
    awk -v id="$1" -v key="$2" -v sect="${3:-}" '
        { sub(/\r$/, "") }
        /^[[:space:]]*#/ { next }
        /^\[\[tool\]\]/ { cur = ""; s = ""; next }
        /^\[tool\.[A-Za-z_]+\]/ { s = $0; sub(/^\[tool\./, "", s); sub(/\].*/, "", s); next }
        /^[[:space:]]*[A-Za-z_]+[[:space:]]*=/ {
            k = $0; sub(/[[:space:]]*=.*/, "", k); gsub(/[[:space:]]/, "", k)
            v = $0; sub(/^[^=]*=[[:space:]]*/, "", v)
            if (match(v, /^"[^"]*"/)) val = substr(v, RSTART + 1, RLENGTH - 2); else val = ""
            if (s == "" && k == "id") cur = val
            if (cur == id && s == sect && k == key && val != "") { print val; exit }
        }' "$REGISTRY"
}

# probe_version <exécutable> [arguments] : premier numéro de version affiché, ou rien.
probe_version() {
    _pe=$1
    shift
    "$_pe" "$@" 2>/dev/null </dev/null | grep -Eo '[0-9]+(\.[0-9]+)+' | head -n 1
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v openssl >/dev/null 2>&1; then
        openssl dgst -sha256 -r "$1" | awk '{print $1}'
    else
        return 1
    fi
}

# checksum_for <fichier checksums.txt> <nom de l'archive> : somme attendue, ou rien.
checksum_for() {
    awk -v f="$2" '{ sub(/\r$/, "") } $2 == f || $2 == "*" f { print $1; exit }' "$1"
}

# verify_sha256 <fichier> <somme attendue> : code 0 si la somme calculée est identique.
verify_sha256() {
    _got=$(sha256_of "$1") || return 2
    [ "$_got" = "$2" ]
}

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g;s/"/\\"/g'; }

# json_field <fichier> <clé> : valeur (texte ou nombre) d'une ligne « "clé": valeur » d'install.json.
json_field() {
    sed -n "s/^[[:space:]]*\"$2\"[[:space:]]*:[[:space:]]*\"\{0,1\}\([^\",]*\)\"\{0,1\},\{0,1\}[[:space:]]*\$/\1/p" "$1" | head -n 1
}

# get_data_dir : pose DATA_DIR, comme resolved_data_dir() de l'application (platformdirs).
get_data_dir() {
    _wd=$(trim "${WDS_DATA_DIR:-}")
    if [ -n "$_wd" ]; then
        DATA_DIR=$_wd
        return
    fi
    if [ -z "${HOME:-}" ]; then
        fail 'la variable HOME est vide : le profil de l utilisateur est introuvable.' 'WDS_DATA_DIR (dossier des données)' ''
    fi
    # platformdirs lit XDG_DATA_HOME sous Linux comme sous macOS, et l'ignore s'il n'est pas absolu.
    _xdg=$(trim "${XDG_DATA_HOME:-}")
    case $_xdg in
        /*) DATA_DIR="$_xdg/WaveDevSecOps" ;;
        *)
            if [ "$OS_NAME" = macos ]; then
                DATA_DIR="$HOME/Library/Application Support/WaveDevSecOps"
            else
                DATA_DIR="$HOME/.local/share/WaveDevSecOps"
            fi
            ;;
    esac
}

# detect_platform : pose OS_NAME (macos|linux), ARCH (x64|arm64).
detect_platform() {
    _os=$(uname -s 2>/dev/null)
    _arch=$(uname -m 2>/dev/null)
    if [ "$SIMULATE" = 1 ]; then
        [ -n "${WDS_INSTALL_SIMULATE_OS:-}" ] && _os=$WDS_INSTALL_SIMULATE_OS
        [ -n "${WDS_INSTALL_SIMULATE_ARCH:-}" ] && _arch=$WDS_INSTALL_SIMULATE_ARCH
    fi
    case $_os in
        Darwin) OS_NAME=macos ;;
        Linux) OS_NAME=linux ;;
        *) fail "système non pris en charge : « $_os » (macOS et Linux seulement ; sous Windows, utilisez install.ps1)." '' '' ;;
    esac
    case $_arch in
        x86_64 | amd64) ARCH=x64 ;;
        arm64 | aarch64) ARCH=arm64 ;;
        *) fail "architecture non prise en charge : « $_arch » (x86_64 et arm64 seulement)." '' '' ;;
    esac
}

# --- Réseau, simulation -------------------------------------------------------------------

sim_log() {
    if [ -n "$SIMLOG" ]; then printf '%s\n' "$1" >>"$SIMLOG"; fi
    return 0
}

simulated_failure() {
    [ "$SIMULATE" = 1 ] || return 1
    case ",$(printf '%s' "${WDS_INSTALL_SIMULATE_FAIL:-}" | tr -d ' ')," in
        *",$1,"*) return 0 ;;
    esac
    return 1
}

init_network() {
    PROXY=''
    _p=${HTTPS_PROXY:-${https_proxy:-}}
    _p=$(trim "$_p")
    if [ -n "$_p" ]; then
        PROXY=$_p
        # curl lit https_proxy / HTTPS_PROXY ; git, uv et pixi lisent les mêmes variables.
        HTTPS_PROXY=$_p
        https_proxy=$_p
        UV_SYSTEM_CERTS=true
        export HTTPS_PROXY https_proxy UV_SYSTEM_CERTS
        info 'Proxy détecté : les téléchargements passent par lui, UV_SYSTEM_CERTS=true.'
    fi
}

# fetch <url> <destination> : téléchargement vers un .part renommé à la fin (jamais de fichier tronqué).
fetch() {
    if [ -s "$2" ]; then
        info "Déjà téléchargé : $(basename "$2")"
        return 0
    fi
    mkdir -p "$(dirname "$2")" || fail "impossible de créer $(dirname "$2")." 'WDS_DATA_DIR (dossier accessible en écriture)' ''
    if [ "$SIMULATE" = 1 ]; then
        sim_log "download $1"
        if simulated_failure download; then
            fail "Le téléchargement de $1 a échoué (simulation)." "$NETWORK_SETTINGS" "$ROUTE_TEXT"
        fi
        case $1 in
            */tools.toml)
                if [ -n "${WDS_INSTALL_SIMULATE_TOOLS_TOML:-}" ]; then
                    cp "$WDS_INSTALL_SIMULATE_TOOLS_TOML" "$2"
                    return 0
                fi
                ;;
        esac
        printf 'simulation' >"$2"
        return 0
    fi
    _part="$2.part"
    rm -f "$_part"
    if command -v curl >/dev/null 2>&1; then
        _fetch_err=$(curl -fsSL --retry 2 --connect-timeout 30 --speed-limit 1024 --speed-time 60 -o "$_part" "$1" 2>&1 </dev/null)
        _fetch_rc=$?
    elif command -v wget >/dev/null 2>&1; then
        _fetch_err=$(wget -q --timeout=60 --tries=3 -O "$_part" "$1" 2>&1 </dev/null)
        _fetch_rc=$?
    else
        fail 'ni curl ni wget ne sont disponibles.' '' "installez curl (paquet du système, ou demandez à l'administrateur), puis relancez ; ou $ROUTE_TEXT"
    fi
    if [ "$_fetch_rc" -ne 0 ] || [ ! -s "$_part" ]; then
        rm -f "$_part"
        fail "Le téléchargement de $1 a échoué (code $_fetch_rc) : $_fetch_err" "$NETWORK_SETTINGS" "$ROUTE_TEXT"
    fi
    mv -f "$_part" "$2" || fail "impossible d'écrire $2." 'WDS_DATA_DIR (dossier accessible en écriture)' ''
}

# run_cmd <commande...> : exécutée sans stdin (le script peut venir d'un tube : curl | sh).
run_cmd() { "$@" </dev/null; }

# --- Étapes -------------------------------------------------------------------------------

# xcode_tools_present : code 0 si les outils en ligne de commande de Xcode sont installés.
xcode_tools_present() {
    if [ "$SIMULATE" = 1 ]; then
        sim_log 'xcode-select -p'
        [ "${WDS_INSTALL_SIMULATE_XCODE:-ok}" = ok ]
        return
    fi
    xcode-select -p >/dev/null 2>&1 </dev/null
}

# find_host_git : pose GIT_PATH, GIT_VERSION, GIT_SOURCE (host|provisioned), ou les vide.
find_host_git() {
    GIT_PATH=''
    GIT_VERSION=''
    GIT_SOURCE=''
    _gmin=$(tool_value git min_version)
    _gp=''
    _gv=''
    if [ "${WDS_INSTALL_FORCE_PROVISION_GIT:-}" = 1 ]; then
        info 'WDS_INSTALL_FORCE_PROVISION_GIT=1 : le git du poste est ignoré.'
    elif [ "$SIMULATE" = 1 ]; then
        _gv=${WDS_INSTALL_SIMULATE_GIT:-}
        [ "$_gv" = none ] && _gv=''
        [ -n "$_gv" ] && _gp=${WDS_INSTALL_SIMULATE_GIT_PATH:-git}
    else
        _gp=$(command -v git 2>/dev/null)
    fi
    if [ -n "$_gp" ] && [ "$_gp" = /usr/bin/git ] && [ "$OS_NAME" = macos ]; then
        # Le git de /usr/bin n'est qu'une doublure : sans les outils Xcode, l'appeler ouvre leur fenêtre d'installation.
        if ! xcode_tools_present; then
            info "/usr/bin/git ignoré : « xcode-select -p » échoue (outils Xcode absents), on ne l'appelle pas."
            sim_log 'skip /usr/bin/git (xcode-select -p échoue)'
            _gp=''
            _gv=''
        fi
    fi
    if [ -n "$_gp" ]; then
        [ "$SIMULATE" = 1 ] || _gv=$(probe_version "$_gp" --version)
        if [ -n "$_gv" ] && version_at_least "$_gv" "$_gmin"; then
            GIT_PATH=$_gp
            GIT_VERSION=$_gv
            GIT_SOURCE=host
            return
        fi
    fi
    _prov="$DATA_DIR/tools/bin/git"
    if [ -x "$_prov" ]; then
        if [ "$SIMULATE" = 1 ]; then
            _gv=$(tool_value git posix provisioned_version)
        else
            _gv=$(probe_version "$_prov" --version)
        fi
        if [ -n "$_gv" ] && version_at_least "$_gv" "$_gmin"; then
            GIT_PATH=$_prov
            GIT_VERSION=$_gv
            GIT_SOURCE=provisioned
        fi
    fi
}

# pixi_triple : nom de plateforme des archives de pixi.
pixi_triple() {
    case "$OS_NAME-$ARCH" in
        linux-x64) printf 'x86_64-unknown-linux-musl' ;;
        linux-arm64) printf 'aarch64-unknown-linux-musl' ;;
        macos-x64) printf 'x86_64-apple-darwin' ;;
        macos-arm64) printf 'aarch64-apple-darwin' ;;
    esac
}

# verify_download <archive> <fichier de sommes> <nom dans le fichier> <libellé>
verify_download() {
    _vd_expected=$(checksum_for "$2" "$3")
    if [ -z "$_vd_expected" ]; then
        _vd_expected=$(awk 'NF >= 1 { print $1; exit }' "$2")
        # Fichier d'une seule somme (pixi : « <somme>  <nom> » ou « <somme> ») ; checksums.txt : somme introuvable.
        [ "$(awk 'END { print NR }' "$2")" = 1 ] || _vd_expected=''
    fi
    if [ -z "$_vd_expected" ]; then
        rm -f "$1"
        fail "$4 : aucune somme de contrôle pour « $3 » dans le fichier de sommes de la release." '' "$ROUTE_TEXT"
    fi
    verify_sha256 "$1" "$_vd_expected"
    _vd_rc=$?
    if [ "$_vd_rc" -eq 2 ]; then
        fail "$4 : aucun outil de somme SHA-256 (sha256sum, shasum, openssl) n'est disponible pour vérifier le téléchargement." '' 'installez sha256sum ou shasum, puis relancez.'
    fi
    if [ "$_vd_rc" -ne 0 ]; then
        rm -f "$1"
        fail "$4 : la somme SHA-256 de « $3 » ne correspond pas à celle de la release (téléchargement corrompu ou intercepté). L'archive est supprimée, rien n'est installé." "$NETWORK_SETTINGS" 'relancez la commande ; si cela persiste, un proxy modifie les téléchargements : demandez à votre administrateur réseau.'
    fi
}

# fetch_sums <url> <destination> <archive> <nom> : en simulation, fabrique la somme (fausse si FAIL=checksum).
fetch_sums() {
    rm -f "$2"
    fetch "$1" "$2"
    if [ "$SIMULATE" = 1 ]; then
        if simulated_failure checksum; then
            printf '%s  %s\n' 0000000000000000000000000000000000000000000000000000000000000000 "$4" >"$2"
        else
            printf '%s  %s\n' "$(sha256_of "$3")" "$4" >"$2"
        fi
    fi
}

install_pixi() {
    PIXI_VERSION=$(tool_value pixi provisioned_version)
    [ -n "$PIXI_VERSION" ] || fail "tools.toml ne donne pas de version de pixi." '' 'récupérez une version à jour de l application.'
    PIXI_BIN="$DATA_DIR/tools/bin/pixi"
    if [ -x "$PIXI_BIN" ]; then
        if [ "$SIMULATE" = 1 ] || [ "$(probe_version "$PIXI_BIN" --version)" = "$PIXI_VERSION" ]; then
            info "pixi $PIXI_VERSION déjà présent."
            return
        fi
    fi
    _triple=$(pixi_triple)
    _name="pixi-$_triple.tar.gz"
    _base="https://github.com/prefix-dev/pixi/releases/download/v$PIXI_VERSION"
    _dl="$DATA_DIR/cache/downloads"
    info "git absent ou antérieur à $GIT_MIN : installation de pixi $PIXI_VERSION dans le profil, puis de git (conda-forge)."
    fetch "$_base/$_name" "$_dl/$_name"
    fetch_sums "$_base/$_name.sha256" "$_dl/$_name.sha256" "$_dl/$_name" "$_name"
    verify_download "$_dl/$_name" "$_dl/$_name.sha256" "$_name" 'Vérification de pixi'
    _tmp="$DATA_DIR/cache/pixi-extract"
    rm -rf "$_tmp"
    mkdir -p "$_tmp" "$DATA_DIR/tools/bin"
    if [ "$SIMULATE" = 1 ]; then
        sim_log "pixi-install $PIXI_VERSION $_triple"
        printf 'simulation' >"$_tmp/pixi"
    else
        tar -xzf "$_dl/$_name" -C "$_tmp" 2>/dev/null </dev/null
    fi
    if [ ! -f "$_tmp/pixi" ]; then
        rm -rf "$_tmp"
        rm -f "$_dl/$_name"
        fail "L'archive de pixi ne contient pas l'exécutable attendu." 'WDS_DATA_DIR (dossier accessible en écriture)' "$ROUTE_TEXT"
    fi
    chmod +x "$_tmp/pixi"
    mv -f "$_tmp/pixi" "$PIXI_BIN" || fail "impossible d'écrire $PIXI_BIN." 'WDS_DATA_DIR (dossier accessible en écriture)' ''
    rm -rf "$_tmp"
    rm -f "$_dl/$_name" "$_dl/$_name.sha256"
}

install_git_with_pixi() {
    GIT_MIN=$(tool_value git min_version)
    install_pixi
    _gv=$(tool_value git posix provisioned_version)
    [ -n "$_gv" ] || fail 'tools.toml ne donne pas de version provisionnée de git pour macOS et Linux.' '' 'récupérez une version à jour de l application.'
    if [ "$SIMULATE" = 1 ]; then
        sim_log "pixi global install git==$_gv (PIXI_HOME=$DATA_DIR/tools)"
        if simulated_failure pixi; then
            fail "« pixi global install git » a échoué (simulation)." "$NETWORK_SETTINGS" "$ROUTE_TEXT"
        fi
        mkdir -p "$DATA_DIR/tools/bin"
        printf 'simulation' >"$DATA_DIR/tools/bin/git"
        chmod +x "$DATA_DIR/tools/bin/git"
    else
        (PIXI_HOME="$DATA_DIR/tools"; export PIXI_HOME; run_cmd "$PIXI_BIN" global install "git==$_gv")
        _rc=$?
        if [ "$_rc" -ne 0 ] || [ ! -x "$DATA_DIR/tools/bin/git" ]; then
            fail "« pixi global install git==$_gv » a échoué (code $_rc) ; la cause est affichée juste au-dessus par pixi." "$NETWORK_SETTINGS" "$ROUTE_TEXT"
        fi
    fi
    GIT_PATH="$DATA_DIR/tools/bin/git"
    GIT_VERSION=$_gv
    GIT_SOURCE=provisioned
}

uv_install_dir() {
    if [ -n "${UV_INSTALL_DIR:-}" ]; then
        printf '%s' "$UV_INSTALL_DIR"
    elif [ -n "${XDG_BIN_HOME:-}" ]; then
        printf '%s' "$XDG_BIN_HOME"
    else
        printf '%s' "$HOME/.local/bin"
    fi
}

# find_host_uv : pose UV_PATH, UV_VERSION, ou les vide.
find_host_uv() {
    UV_PATH=''
    UV_VERSION=''
    _umin=$(tool_value uv min_version)
    if [ "$SIMULATE" = 1 ]; then
        _uv=${WDS_INSTALL_SIMULATE_UV:-}
        if [ -n "$_uv" ] && [ "$_uv" != none ] && version_at_least "$_uv" "$_umin"; then
            UV_PATH=uv
            UV_VERSION=$_uv
        fi
        return
    fi
    for _c in "$(command -v uv 2>/dev/null)" "$(uv_install_dir)/uv"; do
        [ -x "$_c" ] || continue
        _uv=$(probe_version "$_c" --version)
        if [ -n "$_uv" ] && version_at_least "$_uv" "$_umin"; then
            UV_PATH=$_c
            UV_VERSION=$_uv
            return
        fi
    done
}

install_uv() {
    _uvv=$(tool_value uv provisioned_version)
    [ -n "$_uvv" ] || fail 'tools.toml ne donne pas de version provisionnée de uv.' '' 'récupérez une version à jour de l application.'
    _script="$DATA_DIR/cache/downloads/uv-$_uvv-install.sh"
    info "uv absent ou antérieur à $(tool_value uv min_version) : installation de uv $_uvv dans le profil."
    fetch "https://astral.sh/uv/$_uvv/install.sh" "$_script"
    if [ "$SIMULATE" = 1 ]; then
        sim_log "uv-install $_uvv"
        UV_PATH=uv
        UV_VERSION=$_uvv
        return
    fi
    run_cmd sh "$_script"
    _rc=$?
    _uvexe="$(uv_install_dir)/uv"
    if [ "$_rc" -ne 0 ] || [ ! -x "$_uvexe" ]; then
        rm -f "$_script"
        fail "L'installation de uv a échoué (code $_rc) ; la cause est affichée juste au-dessus par l'installeur d'astral. Causes fréquentes : proxy non renseigné, certificats de l'entreprise, antivirus." "$NETWORK_SETTINGS ; UV_INSTALL_DIR (dossier de uv, par défaut ~/.local/bin)" "installez uv vous-même (https://docs.astral.sh/uv/, version $(tool_value uv min_version) ou plus, dans le PATH), puis relancez la commande. $ROUTE_TEXT"
    fi
    UV_PATH=$_uvexe
    UV_VERSION=$(probe_version "$_uvexe" --version)
}

# Un dossier « app » existant n'est remplacé que s'il est vide ou contient l'application
# (pyproject.toml ou .git) : un WDS_DATA_DIR mal placé ne doit pas effacer un dossier de l'utilisateur.
assert_app_dir_replaceable() {
    [ -e "$1" ] || return 0
    [ -f "$1/pyproject.toml" ] && return 0
    [ -e "$1/.git" ] && return 0
    [ -z "$(ls -A "$1" 2>/dev/null)" ] && return 0
    fail "Le dossier « $1 » existe et ne contient pas l'application : il n'est pas modifié." 'WDS_DATA_DIR (dossier réservé à WaveDevSecOps)' 'choisissez un autre WDS_DATA_DIR, ou videz ce dossier « app » vous-même, puis relancez la commande.'
}

# replace_app_dir <dossier prêt> : l'ancienne application (reste d'une voie zip, ou version
# précédente) est mise de côté puis supprimée, jamais effacée avant que la nouvelle soit prête.
replace_app_dir() {
    _old="$APP_DIR.old"
    rm -rf "$_old"
    if [ -e "$APP_DIR" ]; then
        mv "$APP_DIR" "$_old" || fail "impossible de déplacer $APP_DIR (fichier ouvert ?)." 'WDS_DATA_DIR (dossier accessible en écriture)' 'fermez l application, puis relancez la commande.'
    fi
    if ! mv "$1" "$APP_DIR"; then
        [ -e "$_old" ] && mv "$_old" "$APP_DIR"
        fail "impossible de mettre l'application en place dans $APP_DIR." 'WDS_DATA_DIR (dossier accessible en écriture)' ''
    fi
    rm -rf "$_old"
}

# install_app_by_clone : pose APP_REV.
install_app_by_clone() {
    assert_app_dir_replaceable "$APP_DIR"
    if [ "$SIMULATE" = 1 ]; then
        if simulated_failure clone; then
            fail "Le clone de l'application a échoué (simulation)." "$NETWORK_SETTINGS" "$ROUTE_TEXT"
        fi
        if [ -d "$APP_DIR/.git" ]; then
            sim_log "update-clone $APP_DIR"
        else
            sim_log "clone -c core.autocrlf=false $REPO_URL -> $APP_DIR"
            rm -rf "$APP_DIR.partial"
            mkdir -p "$APP_DIR.partial/.git"
            replace_app_dir "$APP_DIR.partial"
        fi
        APP_REV=simulation0000000000000000000000000000000000
        return
    fi
    if [ -d "$APP_DIR/.git" ]; then
        # Mise à jour : récupération puis alignement sur la branche (n'échoue pas sur des fichiers modifiés).
        run_cmd "$GIT_PATH" -c core.autocrlf=false -c http.lowSpeedLimit=1024 -c http.lowSpeedTime=60 -C "$APP_DIR" fetch --depth 1 origin "$REF"
        _c1=$?
        _c2=$_c1
        [ "$_c1" -eq 0 ] && { run_cmd "$GIT_PATH" -c core.autocrlf=false -C "$APP_DIR" reset --hard FETCH_HEAD; _c2=$?; }
        if [ "$_c1" -ne 0 ] || [ "$_c2" -ne 0 ]; then
            fail "La mise à jour git de l'application a échoué (code $_c1/$_c2)." "$NETWORK_SETTINGS" "$ROUTE_TEXT"
        fi
    else
        _partial="$APP_DIR.partial"
        rm -rf "$_partial"   # clone interrompu
        run_cmd "$GIT_PATH" -c core.autocrlf=false -c http.lowSpeedLimit=1024 -c http.lowSpeedTime=60 clone --depth 1 --branch "$REF" "$REPO_URL" "$_partial"
        _rc=$?
        if [ "$_rc" -ne 0 ]; then
            rm -rf "$_partial"
            fail "Le clone de $REPO_URL a échoué (code $_rc)." "$NETWORK_SETTINGS" "$ROUTE_TEXT"
        fi
        replace_app_dir "$_partial"
    fi
    APP_REV=$(run_cmd "$GIT_PATH" -C "$APP_DIR" rev-parse HEAD 2>/dev/null | grep -Eo '[0-9a-f]{40}' | head -n 1)
}

install_app_by_archive() {
    assert_app_dir_replaceable "$APP_DIR"
    _url="$ARCHIVE_URL_BASE/$REF.tar.gz"
    _arc="$DATA_DIR/cache/downloads/wavedevsecops-$(printf '%s' "$REF" | tr '/' '_').tar.gz"
    rm -f "$_arc"   # l'archive d'une branche change : toujours fraîche
    fetch "$_url" "$_arc"
    _staging="$APP_DIR.new"
    rm -rf "$_staging"
    mkdir -p "$_staging"
    if [ "$SIMULATE" = 1 ]; then
        sim_log "zip-extract $_url -> $APP_DIR"
        printf 'simulation' >"$_staging/pyproject.toml"
    else
        # L'archive GitHub contient un seul dossier « wavedevsecops-<ref> » : on le remonte.
        if ! tar -xzf "$_arc" -C "$_staging" --strip-components=1 </dev/null 2>/dev/null; then
            rm -rf "$_staging"
            rm -f "$_arc"
            fail "L'archive n'a pas pu être extraite (fichier corrompu ou « tar » indisponible)." 'WDS_DATA_DIR (dossier accessible en écriture)' "$ROUTE_TEXT"
        fi
        if [ ! -f "$_staging/pyproject.toml" ]; then
            rm -rf "$_staging"
            fail "L'archive ne contient pas l'application attendue (pyproject.toml absent)." 'WDS_INSTALL_REF' "$ROUTE_TEXT"
        fi
    fi
    replace_app_dir "$_staging"
    rm -f "$_arc"
}

run_uv_sync() {
    if [ "$SIMULATE" = 1 ]; then
        sim_log "uv sync --frozen in $APP_DIR"
        if simulated_failure sync; then
            fail "« uv sync » a échoué (simulation)." "$NETWORK_SETTINGS" "$ROUTE_TEXT"
        fi
        return
    fi
    (cd "$APP_DIR" && run_cmd "$UV_PATH" sync --frozen)
    _rc=$?
    if [ "$_rc" -ne 0 ]; then
        fail "« uv sync » a échoué (code $_rc) : les dépendances Python n'ont pas pu être installées." "$NETWORK_SETTINGS" "$ROUTE_TEXT"
    fi
}

# install_gitleaks : archive officielle de la release, vérifiée par le fichier de sommes, extraite dans tools/gitleaks.
install_gitleaks() {
    GL_VERSION=$(tool_value gitleaks provisioned_version)
    [ -n "$GL_VERSION" ] || fail 'tools.toml ne donne pas de version provisionnée de gitleaks.' '' 'récupérez une version à jour de l application.'
    _glexe="$DATA_DIR/tools/gitleaks/gitleaks"
    if [ -x "$_glexe" ]; then
        if [ "$SIMULATE" = 1 ] || [ "$(probe_version "$_glexe" version)" = "$GL_VERSION" ]; then
            info "gitleaks $GL_VERSION déjà présent."
            return
        fi
    fi
    _glos=linux
    [ "$OS_NAME" = macos ] && _glos=darwin
    _name="gitleaks_${GL_VERSION}_${_glos}_${ARCH}.tar.gz"
    _base="https://github.com/gitleaks/gitleaks/releases/download/v$GL_VERSION"
    _dl="$DATA_DIR/cache/downloads"
    info "Installation de gitleaks $GL_VERSION (archive vérifiée par le fichier de sommes de la release)."
    fetch "$_base/$_name" "$_dl/$_name"
    fetch_sums "$_base/gitleaks_${GL_VERSION}_checksums.txt" "$_dl/gitleaks_${GL_VERSION}_checksums.txt" "$_dl/$_name" "$_name"
    verify_download "$_dl/$_name" "$_dl/gitleaks_${GL_VERSION}_checksums.txt" "$_name" 'Vérification de gitleaks'
    _new="$DATA_DIR/tools/gitleaks.new"
    rm -rf "$_new"
    mkdir -p "$_new"
    if [ "$SIMULATE" = 1 ]; then
        sim_log "gitleaks-extract $_name"
        printf 'simulation' >"$_new/gitleaks"
    else
        tar -xzf "$_dl/$_name" -C "$_new" gitleaks </dev/null 2>/dev/null
    fi
    if [ ! -f "$_new/gitleaks" ]; then
        rm -rf "$_new"
        rm -f "$_dl/$_name"
        fail "L'archive de gitleaks ne contient pas l'exécutable attendu." 'WDS_DATA_DIR (dossier accessible en écriture)' "$ROUTE_TEXT"
    fi
    chmod +x "$_new/gitleaks"
    rm -rf "$DATA_DIR/tools/gitleaks"
    mv "$_new" "$DATA_DIR/tools/gitleaks" || fail "impossible d'écrire $DATA_DIR/tools/gitleaks." 'WDS_DATA_DIR (dossier accessible en écriture)' ''
    rm -f "$_dl/$_name" "$_dl/gitleaks_${GL_VERSION}_checksums.txt"
}

# get_registry : pose REGISTRY (tools.toml à côté du script, sinon téléchargé du dépôt).
get_registry() {
    if [ -f "$0" ] && [ -f "$(dirname "$0")/tools.toml" ]; then
        REGISTRY="$(cd "$(dirname "$0")" && pwd)/tools.toml"
        return
    fi
    REGISTRY="$DATA_DIR/cache/tools.toml"
    rm -f "$REGISTRY"
    fetch "$RAW_URL_BASE/$REF/tools.toml" "$REGISTRY"
}

# read_previous_install : pose PREV_FILE (vide si absent) ; refuse un install.json plus récent.
read_previous_install() {
    PREV_FILE=''
    [ -f "$DATA_DIR/install.json" ] || return 0
    PREV_FILE="$DATA_DIR/install.json"
    _sv=$(json_field "$PREV_FILE" schema_version)
    case $_sv in
        '' | *[!0-9]*) PREV_FILE='' ;;   # illisible : on le réécrit
        *)
            if [ "$_sv" -gt "$INSTALLER_VERSION" ]; then
                fail "install.json vient d'une version plus récente de l'application (schema_version $_sv)." '' "mettez à jour l'installeur avec la commande du README à jour ; rien n'a été modifié."
            fi
            ;;
    esac
}

write_install_json() {
    _now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    _first=$_now
    _count=1
    if [ -n "$PREV_FILE" ]; then
        _pf=$(json_field "$PREV_FILE" installed_at)
        [ -n "$_pf" ] && _first=$_pf
        _pc=$(json_field "$PREV_FILE" run_count)
        case $_pc in '' | *[!0-9]*) ;; *) _count=$((_pc + 1)) ;; esac
    fi
    _tmp="$DATA_DIR/install.json.tmp"
    {
        printf '{\n'
        printf '  "schema_version": %s,\n' "$INSTALLER_VERSION"
        printf '  "installed_at": "%s",\n' "$_first"
        printf '  "updated_at": "%s",\n' "$_now"
        printf '  "run_count": %s,\n' "$_count"
        printf '  "duration_s": %s,\n' "$1"
        printf '  "method": "%s",\n' "$METHOD"
        printf '  "app_dir": "%s",\n' "$(json_escape "$APP_DIR")"
        printf '  "versions": {\n%s\n  }\n' "$VERSIONS"
        printf '}\n'
    } >"$_tmp" || fail "impossible d'écrire install.json dans $DATA_DIR." 'WDS_DATA_DIR (dossier accessible en écriture)' ''
    mv -f "$_tmp" "$DATA_DIR/install.json" || fail "impossible d'écrire install.json dans $DATA_DIR." 'WDS_DATA_DIR (dossier accessible en écriture)' ''
}

# add_version <clé> <valeur> : ajoute une ligne à l'objet « versions » d'install.json.
add_version() {
    _line=$(printf '    "%s": "%s"' "$1" "$(json_escape "$2")")
    if [ -n "$VERSIONS" ]; then VERSIONS="$VERSIONS,
$_line"; else VERSIONS=$_line; fi
}

# --- Parcours principal -------------------------------------------------------------------

main() {
    START=$(date +%s)
    VERSIONS=''
    CURRENT_STEP='Préparation'
    detect_platform
    get_data_dir
    METHOD=$(printf '%s' "${WDS_INSTALL_METHOD:-clone}" | tr '[:upper:]' '[:lower:]')
    [ -n "$METHOD" ] || METHOD=clone
    case $METHOD in
        clone | zip) ;;
        *) CURRENT_STEP='Préparation'; fail "WDS_INSTALL_METHOD vaut « $METHOD » : seules les valeurs clone et zip existent." 'WDS_INSTALL_METHOD=clone ou zip' '' ;;
    esac
    REF=$(trim "${WDS_INSTALL_REF:-main}")
    [ -n "$REF" ] || REF=main
    APP_DIR="$DATA_DIR/app"

    step 'Préparation'
    mkdir -p "$DATA_DIR/tools" "$DATA_DIR/cache" || fail "impossible de créer $DATA_DIR." 'WDS_DATA_DIR (dossier accessible en écriture)' ''
    [ "$SIMULATE" = 1 ] && SIMLOG="$DATA_DIR/install.simulation.log"
    read_previous_install
    [ -n "$PREV_FILE" ] && info 'Installation existante : mise à jour (progress.json est conservé).'
    info "Système : $OS_NAME ($ARCH)"
    info "Dossier des données : $DATA_DIR"
    init_network

    step 'Registre des outils (tools.toml)'
    get_registry
    for _id in uv gitleaks pixi; do
        if [ -z "$(tool_value "$_id" provisioned_version)" ]; then
            fail "tools.toml ne déclare pas l'outil « $_id »." '' "récupérez une version à jour de l'application (archive depuis GitHub)."
        fi
    done
    if [ -z "$(tool_value git min_version)" ] || [ -z "$(tool_value git posix provisioned_version)" ]; then
        fail "tools.toml ne déclare pas l'outil « git »." '' "récupérez une version à jour de l'application (archive depuis GitHub)."
    fi
    GIT_MIN=$(tool_value git min_version)

    if [ "$METHOD" = clone ]; then
        step 'git'
        find_host_git
        if [ -n "$GIT_PATH" ]; then
            info "git $GIT_VERSION gardé tel quel ($GIT_SOURCE)."
        else
            install_git_with_pixi
        fi
        add_version git "$GIT_VERSION"
        add_version git_source "$GIT_SOURCE"
        if [ "$GIT_SOURCE" = provisioned ] && [ -z "${PIXI_VERSION:-}" ] && [ -x "$DATA_DIR/tools/bin/pixi" ]; then
            if [ "$SIMULATE" = 1 ]; then
                PIXI_VERSION=$(tool_value pixi provisioned_version)
            else
                PIXI_VERSION=$(probe_version "$DATA_DIR/tools/bin/pixi" --version)
            fi
        fi
    else
        # La voie archive n'a pas besoin de git pour l'installation.
        find_host_git
        if [ -n "$GIT_PATH" ]; then
            add_version git "$GIT_VERSION"
            add_version git_source "$GIT_SOURCE"
        else
            info "Attention : git $GIT_MIN ou plus est introuvable. La voie archive s'en passe pour l'installation, mais les exercices en ont besoin : relancez sans WDS_INSTALL_METHOD=zip pour que l'installeur le provisionne, ou installez git vous-même."
            sim_log 'zip: git absent, non provisionné'
        fi
    fi

    step 'uv'
    find_host_uv
    if [ -n "$UV_PATH" ]; then
        info "uv $UV_VERSION gardé tel quel."
    else
        install_uv
    fi
    add_version uv "$UV_VERSION"

    step "Application ($METHOD)"
    if [ "$METHOD" = clone ]; then
        install_app_by_clone
        add_version app "git:$REF@$APP_REV"
    else
        install_app_by_archive
        add_version app "zip:$REF"
    fi

    step 'Dépendances Python (uv sync)'
    run_uv_sync

    step 'gitleaks'
    install_gitleaks
    add_version gitleaks "$GL_VERSION"
    if [ -n "${PIXI_VERSION:-}" ]; then add_version pixi "$PIXI_VERSION"; fi

    step 'Enregistrement'
    DURATION=$(($(date +%s) - START))
    write_install_json "$DURATION"
    info "install.json écrit dans $DATA_DIR (${DURATION} s)."
    [ -f "$DATA_DIR/progress.json" ] && info 'progress.json conservé tel quel.'

    printf '\nInstallation terminée.\n'
    printf "Lancer l'application :\n"
    printf '    "%s" run --project "%s" wavedevsecops\n' "$UV_PATH" "$APP_DIR"
    if [ "$UV_PATH" != uv ] && ! command -v uv >/dev/null 2>&1; then
        printf 'Ouvrez un nouveau terminal pour que « uv » soit dans le PATH (le profil a été mis à jour par l installeur de uv).\n'
    fi
    if [ -n "$PROXY" ]; then
        printf 'Derrière un proxy, gardez UV_SYSTEM_CERTS=true et NO_PROXY=127.0.0.1,localhost pour les prochains lancements.\n'
    fi
}

[ "${WDS_INSTALL_LIBONLY:-}" = 1 ] || main "$@"
