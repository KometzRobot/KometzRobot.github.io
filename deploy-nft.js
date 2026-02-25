/**
 * deploy-nft.js — Deploy CogCorp NFT collection on Polygon and mint all 10 pieces
 *
 * Usage: node deploy-nft.js
 * Requires: ~0.001 MATIC in wallet, ethers@5
 */

const { ethers } = require("ethers");
const fs = require("fs");
const path = require("path");

const RPC_URL = "https://polygon-bor-rpc.publicnode.com";
const BASE_URL = "https://kometzrobot.github.io";

async function main() {
    // Load wallet
    const walletData = JSON.parse(fs.readFileSync(".wallet-metamask.json", "utf8"));
    const privateKey = walletData.private_key;
    const walletAddress = walletData.address;

    // Load compiled contract
    const abi = JSON.parse(fs.readFileSync("build/CogCorpNFT_sol_CogCorpNFT.abi", "utf8"));
    const bytecode = "0x" + fs.readFileSync("build/CogCorpNFT_sol_CogCorpNFT.bin", "utf8").trim();

    // Connect to Polygon
    const provider = new ethers.providers.JsonRpcProvider(RPC_URL);
    const wallet = new ethers.Wallet(privateKey, provider);

    // Check balance
    const balance = await provider.getBalance(walletAddress);
    const balanceMatic = ethers.utils.formatEther(balance);
    console.log(`Wallet: ${walletAddress}`);
    console.log(`Balance: ${balanceMatic} MATIC`);

    if (balance.isZero()) {
        console.log("\nZero balance. Need MATIC from a faucet.");
        console.log(`Claim at: https://maticfaucet.com`);
        console.log(`Address: ${walletAddress}`);
        process.exit(1);
    }

    // Get gas price
    const gasPrice = await provider.getGasPrice();
    console.log(`Gas price: ${ethers.utils.formatUnits(gasPrice, "gwei")} gwei`);

    // Deploy contract
    console.log("\nDeploying CogCorpNFT contract...");
    const factory = new ethers.ContractFactory(abi, bytecode, wallet);
    const contract = await factory.deploy("CogCorp Propaganda", "COGCORP", {
        gasPrice: gasPrice
    });
    console.log(`TX: ${contract.deployTransaction.hash}`);
    console.log("Waiting for confirmation...");
    await contract.deployed();
    console.log(`Contract deployed at: ${contract.address}`);
    console.log(`PolygonScan: https://polygonscan.com/address/${contract.address}`);

    // Save contract address
    const deployInfo = {
        address: contract.address,
        network: "polygon",
        chainId: 137,
        deployTx: contract.deployTransaction.hash,
        deployer: walletAddress,
        deployedAt: new Date().toISOString(),
        name: "CogCorp Propaganda",
        symbol: "COGCORP"
    };
    fs.writeFileSync("nft-metadata/cogcorp-deployed.json", JSON.stringify(deployInfo, null, 2));
    console.log("Saved deployment info to nft-metadata/cogcorp-deployed.json");

    // Mint all 10 CogCorp pieces
    console.log("\nMinting 10 CogCorp NFTs...");
    const metadataFiles = fs.readdirSync("nft-metadata")
        .filter(f => f.match(/^cogcorp-\d+\.json$/))
        .sort();

    for (const file of metadataFiles) {
        const metadata = JSON.parse(fs.readFileSync(path.join("nft-metadata", file), "utf8"));
        // tokenURI must point to the metadata JSON, not the HTML
        // OpenSea reads this JSON to get name, description, image, animation_url
        const tokenURI = `${BASE_URL}/nft-metadata/${file}`;

        console.log(`  Minting: ${metadata.name}...`);
        const tx = await contract.mint(walletAddress, tokenURI, { gasPrice });
        const receipt = await tx.wait();
        const tokenId = receipt.events[0].args.tokenId.toString();
        console.log(`    Token #${tokenId} minted. TX: ${tx.hash}`);
    }

    // Final balance
    const finalBalance = await provider.getBalance(walletAddress);
    const spent = balance.sub(finalBalance);
    console.log(`\nDone! All ${metadataFiles.length} NFTs minted.`);
    console.log(`Gas spent: ${ethers.utils.formatEther(spent)} MATIC`);
    console.log(`Remaining: ${ethers.utils.formatEther(finalBalance)} MATIC`);
    console.log(`\nView on OpenSea: https://opensea.io/collection/cogcorp-propaganda`);
    console.log(`View on PolygonScan: https://polygonscan.com/address/${contract.address}`);
}

main().catch(err => {
    console.error("Error:", err.message);
    process.exit(1);
});
