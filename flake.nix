{
  description = "zup - ClickUp time tracking Qt app";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};

        clickup-python-sdk = pkgs.python3Packages.buildPythonPackage rec {
          pname = "clickup-python-sdk";
          version = "2.0.1";
          format = "wheel";

          src = pkgs.fetchurl {
            url = "https://files.pythonhosted.org/packages/b4/9c/2eba76d6e1f07b35fa670652360011636057feff1df6f1ede02b63efa30c/clickup_python_sdk-2.0.1-py3-none-any.whl";
            sha256 = "sha256-paJT2oQ5sTAWe5ZlSOlmb7I1H420OG+/npqleHF36/8=";
          };

          propagatedBuildInputs = with pkgs.python3Packages; [
            requests
          ];
        };

        zup = pkgs.python3Packages.buildPythonApplication {
          pname = "zup";
          version = "0.1.0";
          pyproject = true;

          src = ./.;

          build-system = with pkgs.python3Packages; [
            hatchling
          ];

          dependencies = with pkgs.python3Packages; [
            appdirs
            click
            pendulum
            pyside6
            clickup-python-sdk
          ];
        };
      in {
        packages.default = zup;

        devShells.default = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages (ps:
              with ps; [
                appdirs
                click
                pendulum
                pyside6
                clickup-python-sdk
              ]))
            pkgs.pyright
          ];
        };
      }
    );
}
