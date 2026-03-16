{pkgs ? import <nixpkgs> {}}: let
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
      certifi
      charset-normalizer
      idna
      urllib3
    ];
  };
in
  pkgs.mkShell {
    packages = [
      pkgs.python3
      pkgs.python3Packages.pyside6
      pkgs.python3Packages.appdirs
      pkgs.python3Packages.pendulum
      pkgs.python3Packages.requests
      pkgs.python3Packages.click
      pkgs.pyright
      clickup-python-sdk
    ];

    env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.stdenv.cc.cc.lib
      pkgs.libz
    ];
  }
