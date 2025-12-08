{
  description = "EMF Orga Directory";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      treefmt-nix,
    }:
    let
      inherit (nixpkgs) lib;

      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems =
        f:
        lib.genAttrs supportedSystems (
          system:
          f (rec {
            inherit system;
            pkgs = nixpkgs.legacyPackages.${system};
            python = pkgs.python314;
            pythonSet =
              (pkgs.callPackage pyproject-nix.build.packages {
                inherit python;
              }).overrideScope
                (
                  lib.composeManyExtensions [
                    pyproject-build-systems.overlays.wheel
                    overlay
                  ]
                );
            devVirtualenv = pythonSet.mkVirtualEnv "orgahome-env" workspace.deps.all;
            virtualenv = pythonSet.mkVirtualEnv "orgahome-env" workspace.deps.default;
            inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;
            treefmtEval =
              let
                ruff = pythonSet.ruff // {
                  meta = pythonSet.ruff.meta // {
                    mainProgram = "ruff";
                  };
                };
              in
              treefmt-nix.lib.evalModule pkgs {
                imports = [ ./treefmt.nix ];

                # Use ruff version from pyproject.toml, not nixpkgs.
                programs.ruff-check.package = ruff;
                programs.ruff-format.package = ruff;
              };
          })
        );

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };
    in
    {
      devShells = forAllSystems (
        {
          pkgs,
          pythonSet,
          devVirtualenv,
          treefmtEval,
          ...
        }:
        {
          default = pkgs.mkShell {
            packages = [
              devVirtualenv
              pkgs.uv
              (treefmtEval.config.build.wrapper) # provide treefmt CLI
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            };
            shellHook = ''
              unset PYTHONPATH
              export VIRTUAL_ENV=$(dirname $(dirname $(command -v python3)))
              export FLASK_APP=orgahome
              export REPO_ROOT=$(git rev-parse --show-toplevel)
            '';
          };
        }
      );

      packages = forAllSystems (
        {
          pkgs,
          virtualenv,
          mkApplication,
          pythonSet,
          ...
        }:
        rec {
          default = mkApplication {
            venv = virtualenv;
            package = pythonSet.orgahome;
          };
          dist =
            pkgs.runCommand "orgahome-dist"
              {
                nativeBuildInputs = [ default ];
              }
              ''
                orgahome compilestatic -d $out
              '';
          container = pkgs.dockerTools.streamLayeredImage {
            name = "orgahome";
            fakeRootCommands = ''
              ${pkgs.dockerTools.shadowSetup}
              groupadd -r orgahome
              useradd -r -g orgahome orgahome
            '';
            enableFakechroot = true;
            config = {
              Entrypoint = [ "${default}/bin/orgahome" ];
              User = "orgahome:orgahome";
              Cmd = [
                "uvicorn"
              ];
              ExposedPorts = {
                "5000/tcp" = { };
              };
              Env = [
                "ORGAHOME_DIST_ROOT=${dist}"
                "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
              ];
            };
          };

          upload-container = pkgs.writeShellApplication {
            name = "upload-container";

            runtimeInputs = [
              pkgs.podman
            ];

            text = builtins.readFile ./hack/upload-container.sh;
          };
        }
      );

      formatter = forAllSystems ({ treefmtEval, ... }: treefmtEval.config.build.wrapper);

      checks = forAllSystems (
        {
          treefmtEval,
          pkgs,
          devVirtualenv,
          ...
        }:
        {
          formatting = treefmtEval.config.build.check self;
          ty =
            pkgs.runCommand "ty"
              {
                nativeBuildInputs = [ devVirtualenv ];
                inherit self;
              }
              ''
                export VIRTUAL_ENV=$(dirname $(dirname $(command -v python3)))
                ty check $self
                touch $out  # success
              '';
        }
      );
    };
}
