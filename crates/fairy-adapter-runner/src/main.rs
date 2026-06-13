use serde::Deserialize;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize)]
struct AdapterManifest {
    schema_version: String,
    id: String,
    name: String,
    kind: String,
    source: Source,
    capabilities: Vec<String>,
    entrypoints: Entrypoints,
    contracts: Contracts,
    safety: Safety,
    validation: Validation,
}

#[derive(Debug, Deserialize)]
struct Source {
    upstream: String,
    fork: Option<String>,
    package: Option<String>,
    local_path_hint: Option<String>,
    license: String,
    notes: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Entrypoints {
    #[serde(rename = "import")]
    import_stmt: String,
    construct: String,
    run: String,
    optional: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
struct Contracts {
    inputs: Vec<String>,
    outputs: Vec<String>,
    evidence: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct Safety {
    boundaries: Vec<String>,
    forbidden_claims: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct Validation {
    checks: Vec<String>,
    minimum_artifacts: Vec<String>,
}

fn require(condition: bool, message: impl Into<String>) -> Result<(), String> {
    if condition {
        Ok(())
    } else {
        Err(message.into())
    }
}

fn require_non_empty(value: &str, label: &str) -> Result<(), String> {
    require(
        !value.trim().is_empty(),
        format!("{label} must be non-empty"),
    )
}

fn require_non_empty_list(values: &[String], label: &str) -> Result<(), String> {
    require(
        !values.is_empty(),
        format!("{label} must be a non-empty list"),
    )?;
    for (index, value) in values.iter().enumerate() {
        require_non_empty(value, &format!("{label}[{index}]"))?;
    }
    Ok(())
}

fn validate_adapter(path: &Path) -> Result<AdapterManifest, String> {
    let text = fs::read_to_string(path)
        .map_err(|err| format!("{}: failed to read: {err}", path.display()))?;
    let manifest: AdapterManifest = serde_json::from_str(&text)
        .map_err(|err| format!("{}: invalid JSON: {err}", path.display()))?;

    require(
        manifest.schema_version == "1.0",
        "schema_version must be 1.0",
    )?;
    require_non_empty(&manifest.id, "id")?;
    require_non_empty(&manifest.name, "name")?;
    require(
        matches!(
            manifest.kind.as_str(),
            "external-reconstruction"
                | "evaluation-harness"
                | "domain-tool"
                | "renderer"
                | "memory-system"
        ),
        format!("unsupported adapter kind: {}", manifest.kind),
    )?;

    require_non_empty(&manifest.source.upstream, "source.upstream")?;
    require_non_empty(&manifest.source.license, "source.license")?;
    if let Some(fork) = &manifest.source.fork {
        require_non_empty(fork, "source.fork")?;
    }
    if let Some(package) = &manifest.source.package {
        require_non_empty(package, "source.package")?;
    }
    if let Some(local_path_hint) = &manifest.source.local_path_hint {
        require_non_empty(local_path_hint, "source.local_path_hint")?;
    }
    if let Some(notes) = &manifest.source.notes {
        require_non_empty(notes, "source.notes")?;
    }

    require_non_empty_list(&manifest.capabilities, "capabilities")?;
    require_non_empty(&manifest.entrypoints.import_stmt, "entrypoints.import")?;
    require_non_empty(&manifest.entrypoints.construct, "entrypoints.construct")?;
    require_non_empty(&manifest.entrypoints.run, "entrypoints.run")?;
    if let Some(optional) = &manifest.entrypoints.optional {
        require_non_empty_list(optional, "entrypoints.optional")?;
    }

    require_non_empty_list(&manifest.contracts.inputs, "contracts.inputs")?;
    require_non_empty_list(&manifest.contracts.outputs, "contracts.outputs")?;
    require_non_empty_list(&manifest.contracts.evidence, "contracts.evidence")?;
    require_non_empty_list(&manifest.safety.boundaries, "safety.boundaries")?;
    require_non_empty_list(&manifest.safety.forbidden_claims, "safety.forbidden_claims")?;
    require_non_empty_list(&manifest.validation.checks, "validation.checks")?;
    require_non_empty_list(
        &manifest.validation.minimum_artifacts,
        "validation.minimum_artifacts",
    )?;

    Ok(manifest)
}

fn discover_default_manifests() -> Result<Vec<PathBuf>, String> {
    let adapters_dir = Path::new("adapters");
    let mut paths = Vec::new();
    let entries = fs::read_dir(adapters_dir)
        .map_err(|err| format!("failed to read adapters directory: {err}"))?;
    for entry in entries {
        let entry = entry.map_err(|err| format!("failed to read adapter entry: {err}"))?;
        let path = entry.path();
        if path
            .file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| name.ends_with(".adapter.json"))
        {
            paths.push(path);
        }
    }
    paths.sort();
    require(!paths.is_empty(), "no adapter manifests found")?;
    Ok(paths)
}

fn main() -> Result<(), String> {
    let mut args = env::args().skip(1).collect::<Vec<_>>();
    if args.first().is_some_and(|arg| arg == "validate") {
        args.remove(0);
    }

    let paths = if args.is_empty() {
        discover_default_manifests()?
    } else {
        args.into_iter().map(PathBuf::from).collect()
    };

    for path in paths {
        let manifest = validate_adapter(&path)?;
        println!(
            "adapter validation passed: {} ({})",
            path.display(),
            manifest.id
        );
    }

    Ok(())
}
