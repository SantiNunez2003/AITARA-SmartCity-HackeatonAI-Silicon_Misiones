<#
.SYNOPSIS
    Script de referencia PowerShell para carga de capas IGN, Natural Earth e IDE Posadas
    hacia el esquema `staging` en PostgreSQL/PostGIS mediante `shp2pgsql` y `ogr2ogr`.

.DESCRIPTION
    Forma parte del portfolio académico AE4 SIG (AITARA + IGN + IDE Posadas).
    Documenta y permite ejecutar los comandos estándar de GDAL (`ogr2ogr`) y PostGIS
    (`shp2pgsql` dentro del contenedor Docker `ae4_postgis`) para ingestar shapefiles y
    GeoJSON descargados por `descargar_ign_ide.py` hacia el esquema `staging`, previo a su
    normalización SQL hacia `sig_ae4`.

    Por defecto imprime los comandos listos para ejecutar (modo referencia segura).
    Pase `-Execute` para correrlos efectivamente contra `ae4_postgis` / PostgreSQL.

.EXAMPLE
    .\ae4_sig\scripts\cargar_ogr2ogr_referencia.ps1
    .\ae4_sig\scripts\cargar_ogr2ogr_referencia.ps1 -Execute
#>

[CmdletBinding()]
param(
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

$SigDir = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $SigDir ".env"
$DatosExternosDir = Join-Path $SigDir "datos_externos"

# Cargar variables desde ae4_sig\.env si existe
$EnvVars = @{
    POSTGRES_HOST     = "localhost"
    POSTGRES_PORT     = "5433"
    POSTGRES_DB       = "aitara_ae4_sig"
    POSTGRES_USER     = "ae4_user"
    POSTGRES_PASSWORD = "ae4_sig_2026_local"
}
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match "^([^=]+)=(.*)$") {
            $EnvVars[$matches[1].Trim()] = $matches[2].Trim()
        }
    }
}

$PgHost = $EnvVars["POSTGRES_HOST"]
$PgPort = $EnvVars["POSTGRES_PORT"]
$PgDb = $EnvVars["POSTGRES_DB"]
$PgUser = $EnvVars["POSTGRES_USER"]
$PgPassword = $EnvVars["POSTGRES_PASSWORD"]

$PgConn = "PG:host=$PgHost port=$PgPort dbname=$PgDb user=$PgUser password=$PgPassword"

Write-Host "=== Referencia AE4 SIG: Carga de datos externos hacia esquema 'staging' ===" -ForegroundColor Cyan
Write-Host "Base destino : ${PgHost}:${PgPort}/${PgDb} (usuario: $PgUser)"
Write-Host "Datos origen : $DatosExternosDir"
Write-Host "Modo         : $(if ($Execute) { 'EJECUCION REAL' } else { 'SOLO REFERENCIA (use -Execute para correr)' })`n"

# -----------------------------------------------------------------------------
# 1. MÉTODO SHAPEFILE NATIVO POSTGIS: shp2pgsql (dentro del contenedor ae4_postgis)
#    Nota: docker-compose.yml monta ./datos_externos en /datos_externos:ro
# -----------------------------------------------------------------------------
$ShpZipLocal = Join-Path $DatosExternosDir "ide_delegaciones_shp.zip"
$ShpExtractLocal = Join-Path $DatosExternosDir "ide_delegaciones_shp"
$ShpContainerPath = "/datos_externos/ide_delegaciones_shp/DELEGACIONES_MUNICIPALES_POSADAS_20250.shp"

Write-Host "[1] Shapefile IDE Posadas (Delegaciones Municipales) vía shp2pgsql:" -ForegroundColor Yellow
Write-Host "    Expand-Archive -Path `"$ShpZipLocal`" -DestinationPath `"$ShpExtractLocal`" -Force"
Write-Host "    docker exec -i ae4_postgis shp2pgsql -I -s 4326 -d -W UTF-8 $ShpContainerPath staging.ide_delegaciones_shp | docker exec -i ae4_postgis psql -U $PgUser -d $PgDb`n"

if ($Execute) {
    if (-not (Test-Path $ShpZipLocal)) {
        throw "No existe $ShpZipLocal. Ejecute primero ae4_sig\scripts\descargar_ign_ide.py."
    }
    Expand-Archive -Path $ShpZipLocal -DestinationPath $ShpExtractLocal -Force
    docker exec -i ae4_postgis shp2pgsql -I -s 4326 -d -W UTF-8 $ShpContainerPath staging.ide_delegaciones_shp |
        docker exec -i ae4_postgis psql -U $PgUser -d $PgDb
}

# -----------------------------------------------------------------------------
# 2. MÉTODO GDAL / OGR2OGR: Shapefile (.zip /vsizip/) y GeoJSON IGN + IDE Posadas
#    Equivalente multi-formato (GeoJSON, Shapefile, GeoPackage) hacia staging
# -----------------------------------------------------------------------------
$ShpZipVsizip = "/vsizip/" + ($ShpZipLocal -replace "\\", "/") + "/DELEGACIONES_MUNICIPALES_POSADAS_20250.shp"
$Ogr2OgrBin = Get-Command ogr2ogr -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $Ogr2OgrBin -and (Test-Path "C:\Program Files\QGIS 4.2.1\bin\ogr2ogr.exe")) {
    $Ogr2OgrBin = "C:\Program Files\QGIS 4.2.1\bin\ogr2ogr.exe"
}
$OgrExeDisplay = if ($Ogr2OgrBin) { "`"$Ogr2OgrBin`"" } else { "ogr2ogr" }

$OgrShpCmd = @(
    $OgrExeDisplay, "--config", "SHAPE_ENCODING", "ISO-8859-1",
    "-f", "PostgreSQL", "`"$PgConn`"",
    "`"$ShpZipVsizip`"",
    "-nln", "staging.ide_delegaciones_ogr_demo",
    "-lco", "SCHEMA=staging",
    "-lco", "GEOMETRY_NAME=geom",
    "-lco", "FID=gid",
    "-nlt", "PROMOTE_TO_MULTI",
    "-t_srs", "EPSG:4326",
    "-overwrite"
) -join " "

Write-Host "[2] Equivalente ogr2ogr directo desde ZIP Shapefile (/vsizip/, codificación DBF ISO-8859-1):" -ForegroundColor Yellow
Write-Host "    $OgrShpCmd`n"

if ($Execute) {
    if (-not $Ogr2OgrBin) {
        throw "No se encontró 'ogr2ogr' en el PATH ni en C:\Program Files\QGIS 4.2.1\bin\ogr2ogr.exe."
    }
    $env:SHAPE_ENCODING = "ISO-8859-1"
    & $Ogr2OgrBin -f PostgreSQL $PgConn $ShpZipVsizip `
        -nln staging.ide_delegaciones_ogr_demo `
        -lco SCHEMA=staging `
        -lco GEOMETRY_NAME=geom `
        -lco FID=gid `
        -nlt PROMOTE_TO_MULTI `
        -t_srs EPSG:4326 `
        -overwrite
    if ($LASTEXITCODE -ne 0) {
        throw "ogr2ogr falló al cargar $ShpZipVsizip (exit=$LASTEXITCODE)"
    }
}

$GeoJsonLayers = @(
    # Escala regional: Natural Earth + IGN
    @{ File = "ne_paises_sudamerica.geojson";        Table = "staging.ne_paises";                 GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ign_provincias.geojson";              Table = "staging.ign_provincias";            GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ign_departamentos.geojson";           Table = "staging.ign_departamentos";         GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ign_localidades.geojson";             Table = "staging.ign_localidades";           GeomType = "POINT" },
    @{ File = "ign_cursos_agua.geojson";             Table = "staging.ign_cursos_agua";           GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ign_vial_nacional.geojson";           Table = "staging.ign_vial_nacional";         GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ign_vial_provincial.geojson";         Table = "staging.ign_vial_provincial";       GeomType = "PROMOTE_TO_MULTI" },
    # Escala urbana: IDE Posadas
    @{ File = "ide_delegaciones.geojson";            Table = "staging.ide_delegaciones";          GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ide_semaforos.geojson";               Table = "staging.ide_semaforos";             GeomType = "POINT" },
    @{ File = "ide_escuelas.geojson";                Table = "staging.ide_escuelas";              GeomType = "POINT" },
    @{ File = "ide_paradas.geojson";                 Table = "staging.ide_paradas";               GeomType = "POINT" },
    @{ File = "ide_manos_unicas.geojson";            Table = "staging.ide_manos_unicas";          GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ide_asfalto_sobre_empedrado.geojson"; Table = "staging.ide_asfalto_empedrado";     GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ide_ciclovias.geojson";               Table = "staging.ide_ciclovias";             GeomType = "PROMOTE_TO_MULTI" },
    @{ File = "ide_radios_censales_2022.geojson";    Table = "staging.ide_radios_censales_2022";  GeomType = "PROMOTE_TO_MULTI" }
)

Write-Host "[3] Carga masiva de GeoJSON IGN / Natural Earth / IDE Posadas vía ogr2ogr:" -ForegroundColor Yellow
foreach ($layer in $GeoJsonLayers) {
    $srcPath = Join-Path $DatosExternosDir $layer.File
    $tableName = $layer.Table
    $nlt = $layer.GeomType

    $cmdPreview = "ogr2ogr -f PostgreSQL `"$PgConn`" `"$srcPath`" -nln $tableName -lco GEOMETRY_NAME=geom -lco FID=gid -nlt $nlt -t_srs EPSG:4326 -overwrite"
    Write-Host "    $cmdPreview"

    if ($Execute) {
        if (-not $Ogr2OgrBin) {
            throw "No se encontró 'ogr2ogr' en el PATH ni en C:\Program Files\QGIS 4.2.1\bin\ogr2ogr.exe."
        }
        if (-not (Test-Path $srcPath)) {
            Write-Warning "Archivo omitido (no encontrado): $srcPath"
            continue
        }
        & $Ogr2OgrBin -f PostgreSQL $PgConn $srcPath `
            -nln $tableName `
            -lco GEOMETRY_NAME=geom `
            -lco FID=gid `
            -nlt $nlt `
            -t_srs EPSG:4326 `
            -overwrite
        if ($LASTEXITCODE -ne 0) {
            throw "ogr2ogr falló al cargar $($layer.File) en $tableName (exit=$LASTEXITCODE)"
        }
    }
}

Write-Host "`n[OK] Referencia completada. Normalice desde 'staging.*' hacia 'sig_ae4.*' vía SQL." -ForegroundColor Green
