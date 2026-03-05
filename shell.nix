{ pkgs ? import <nixpkgs> {} }:

let
  optimizeStaged = pkgs.writeShellScriptBin "optimize-staged" ''
    # Get the list of STAGED files (added but not yet committed)
    STAGED_FILES=$(${pkgs.git}/bin/git diff --cached --name-only --diff-filter=ACM)

    if [ -z "$STAGED_FILES" ]; then
      echo "⚠️  No staged files found. Run 'git add <file>' first."
      exit 0
    fi

    echo "🔍 Checking staged files for images..."

    # Filter for PNGs and JPEGs from the staged list
    # Using 'grep -i' for case-insensitive matching
    PNGS=$(echo "$STAGED_FILES" | grep -i "\.png$" || true)
    JPGS=$(echo "$STAGED_FILES" | grep -iE "\.jpe?g$" || true)

    if [ -n "$PNGS" ]; then
      echo "🚀 Optimizing staged PNGs..."
      echo "$PNGS" | xargs -I {} ${pkgs.oxipng}/bin/oxipng -o 4 --strip all "{}"
    fi

    if [ -n "$JPGS" ]; then
      echo "🚀 Optimizing staged JPEGs..."
      echo "$JPGS" | xargs -I {} ${pkgs.jpegoptim}/bin/jpegoptim --strip-all "{}"
    fi

    echo "------------------------------------------------"
    echo "✅ Done! Files have been modified on disk."
    echo "🚨 IMPORTANT: You must run 'git add' again to stage the compressed versions."
  '';
in
pkgs.mkShell {
  buildInputs = with pkgs; [
    oxipng
    jpegoptim
    git
    optimizeStaged
  ];

  shellHook = ''
    echo "🖼️  Asset Environment Loaded"
    echo "---------------------------"
    echo "Workflow:"
    echo " 1. git add <image.png>"
    echo " 2. optimize-staged"
    echo " 3. git add <image.png> (to restage optimized version)"
    echo " 4. git commit"
  '';
}
