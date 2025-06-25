{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  packages = [
    pkgs.python3
    pkgs.python312Packages.pyside6
    pkgs.python312Packages.appdirs
    pkgs.python312Packages.pendulum
    pkgs.python312Packages.requests
  ];

  env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
    pkgs.stdenv.cc.cc.lib
    pkgs.libz
  ];

  shellHook = ''
    alias vim='uv run ~/mitt/nixvim/result/bin/nvim'
  '';
}
