{pkgs ? import <nixpkgs> {}}:
pkgs.mkShell {
  packages = [
    pkgs.rustc
    pkgs.cargo
    pkgs.python3
    pkgs.python3Packages.pyside6
    pkgs.python3Packages.appdirs
    pkgs.python3Packages.pendulum
    pkgs.python3Packages.requests
  ];

  env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
    pkgs.stdenv.cc.cc.lib
    pkgs.libz
  ];
}
