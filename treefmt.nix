{ ... }:
{
  projectRootFile = "flake.nix";

  # Nix
  programs.deadnix.enable = true;
  programs.nixfmt.enable = true;

  # Python
  programs.ruff-check.enable = true;
  programs.ruff-format.enable = true;

  # TOML
  programs.taplo.enable = true;

  # JS/CSS/JSON
  programs.deno = {
    enable = true;
    excludes = [ "*.html" ]; # makes a mess of Jinja
  };

  # Jinja templates
  programs.djlint.enable = true;

  # GitHub Actions
  programs.zizmor.enable = true;
}
