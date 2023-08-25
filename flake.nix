{
  description = "charli3-backend-v2";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs?ref=nixos-22.11";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    # For plutip-server
    cardano-transaction-lib = {
      url = "github:Plutonomicon/cardano-transaction-lib?ref=develop";
    };
    cardano-node = {
      follows = "cardano-transaction-lib/cardano-node";
    };
    ogmios = {
      follows = "cardano-transaction-lib/ogmios";
    };
    kupo-nixos = {
      follows = "cardano-transaction-lib/kupo-nixos";
    };
    plutip-core = {
      url = "github:mlabs-haskell/plutip?ref=plutip-core";
    };
    cachix = {
      url = "github:cachix/cachix/latest";
    };
  };

  outputs = inputs @ { flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = inputs.nixpkgs.lib.systems.flakeExposed;

      perSystem = { config, self', inputs', pkgs, system, ... }: {
        formatter = pkgs.nixpkgs-fmt;

        devShells.default =
          pkgs.mkShell {
            nativeBuildInputs = [
              pkgs.poetry
              inputs'.ogmios.packages."ogmios:exe:ogmios"
              inputs'.cardano-node.packages.cardano-node
              inputs'.kupo-nixos.packages.kupo
              inputs'.plutip-core.packages."plutip-core:exe:local-cluster"
              inputs'.cachix.packages.cachix
            ];
          };
      };
    };
}
