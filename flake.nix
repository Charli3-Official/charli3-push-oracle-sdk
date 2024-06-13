{
  description = "charli3-backend-v2";

  inputs = {
    nixpkgs.follows = "haskell-nix/nixpkgs-unstable";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    hackage-nix = {
      url = "github:input-output-hk/hackage.nix";
      flake = false;
    };
    iohk-nix = {
      url = "github:input-output-hk/iohk-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    haskell-nix = {
      url = "github:input-output-hk/haskell.nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.hackage.follows = "hackage-nix";
    };
    plutip = {
      url = "github:mlabs-haskell/plutip?ref=gergely/version-bump";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        iohk-nix.follows = "iohk-nix";
        haskell-nix.follows = "haskell-nix";
        hackage-nix.follows = "hackage-nix";
        cardano-node.follows = "cardano-node";
      };
    };
    cardano-transaction-lib = {
      url = "github:Plutonomicon/cardano-transaction-lib?ref=develop";
    };
    cardano-node = {
      url = "github:input-output-hk/cardano-node?ref=8.1.1";
    };
    ogmios = {
      # url = "github:CardanoSolutions/ogmios?ref=dabab146d12162f7efb09da761b8f9dc9dcc4c67";
      url = "github:CardanoSolutions/ogmios/v6.1.0";
      flake = false;
    };
    ogmios-nixos = {
      url = "github:mlabs-haskell/ogmios-nixos?ref=78e829e9ebd50c5891024dcd1004c2ac51facd80";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        iohk-nix.follows = "iohk-nix";
        haskell-nix.follows = "haskell-nix";
        cardano-node.follows = "cardano-node";
        ogmios-src.follows = "ogmios";
      };
    };
    kupo = {
      url = "github:CardanoSolutions/kupo?ref=v2.2.0";
      flake = false;
    };
    kupo-nixos = {
      url = "github:mlabs-haskell/kupo-nixos?ref=6f89cbcc359893a2aea14dd380f9a45e04c6aa67";
      inputs.kupo.follows = "kupo";
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
              # Fix Ogmios
              # inputs'.ogmios-nixos.packages."ogmios:exe:ogmios"
              inputs'.cardano-node.packages.cardano-node
              inputs'.kupo-nixos.packages.kupo
              inputs'.plutip-core.packages."plutip-core:exe:local-cluster"
              inputs'.cachix.packages.cachix
            ];
          };
      };
    };
}
