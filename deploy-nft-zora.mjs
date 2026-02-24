/**
 * deploy-nft-zora.mjs — Deploy CogCorp NFT collection on Zora L2
 *
 * Uses Zora Protocol SDK to create ERC-1155 tokens on Zora mainnet.
 * Gas on Zora L2 is sub-cent, so total deployment cost is ~$0.05-0.50.
 *
 * Usage: node deploy-nft-zora.mjs
 * Requires: Tiny amount of ETH on Zora chain
 */

import { createPublicClient, createWalletClient, http, formatEther } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { zora } from "viem/chains";
import { createCreatorClient } from "@zoralabs/protocol-sdk";
import { readFileSync, writeFileSync, readdirSync } from "fs";
import { join } from "path";

const RPC_URL = "https://rpc.zora.energy";
const BASE_URL = "https://kometzrobot.github.io";

async function main() {
    // Load wallet
    const walletData = JSON.parse(readFileSync(".wallet-metamask.json", "utf8"));
    const privateKey = walletData.private_key.startsWith("0x")
        ? walletData.private_key
        : `0x${walletData.private_key}`;
    const account = privateKeyToAccount(privateKey);

    console.log(`Wallet: ${account.address}`);

    // Create clients
    const publicClient = createPublicClient({
        chain: zora,
        transport: http(RPC_URL),
    });

    const walletClient = createWalletClient({
        chain: zora,
        transport: http(RPC_URL),
        account,
    });

    // Check balance
    const balance = await publicClient.getBalance({ address: account.address });
    const balanceEth = formatEther(balance);
    console.log(`Zora ETH balance: ${balanceEth}`);

    if (balance === 0n) {
        console.log("\nZero balance on Zora. Need ETH bridged to Zora L2.");
        console.log("Bridge at: https://bridge.zora.energy/");
        console.log(`Address: ${account.address}`);
        console.log("Even $0.50 of ETH is enough for all 10 mints.");
        process.exit(1);
    }

    // Create Zora creator client
    const creatorClient = createCreatorClient({ chainId: zora.id, publicClient });

    // Load CogCorp metadata files
    const metadataFiles = readdirSync("nft-metadata")
        .filter(f => f.match(/^cogcorp-\d+\.json$/))
        .sort();

    console.log(`\nFound ${metadataFiles.length} CogCorp metadata files.`);

    // Create first token (this also deploys the contract)
    const firstMetadata = JSON.parse(readFileSync(join("nft-metadata", metadataFiles[0]), "utf8"));
    const collectionMetadata = JSON.parse(readFileSync("nft-metadata/cogcorp-collection.json", "utf8"));

    console.log("\nCreating collection + first token...");
    console.log(`  ${firstMetadata.name}`);

    const { parameters: createParams, contractAddress } = await creatorClient.create1155({
        contract: {
            name: "CogCorp Propaganda",
            uri: `${BASE_URL}/nft-metadata/cogcorp-collection.json`,
        },
        token: {
            tokenMetadataURI: `${BASE_URL}/nft-metadata/${metadataFiles[0]}`,
        },
        account: account.address,
    });

    const { request: createRequest } = await publicClient.simulateContract(createParams);
    const createHash = await walletClient.writeContract(createRequest);
    const createReceipt = await publicClient.waitForTransactionReceipt({ hash: createHash });

    console.log(`  Contract: ${contractAddress}`);
    console.log(`  TX: ${createHash}`);
    console.log(`  Status: ${createReceipt.status}`);

    // Save deployment info
    const deployInfo = {
        contractAddress,
        network: "zora",
        chainId: 7777777,
        deployTx: createHash,
        deployer: account.address,
        deployedAt: new Date().toISOString(),
        name: "CogCorp Propaganda",
        standard: "ERC-1155",
        tokens: [{ file: metadataFiles[0], tx: createHash }],
    };

    // Mint remaining tokens on existing contract
    for (let i = 1; i < metadataFiles.length; i++) {
        const metadata = JSON.parse(readFileSync(join("nft-metadata", metadataFiles[i]), "utf8"));
        console.log(`\n  Minting: ${metadata.name}...`);

        const { parameters: mintParams } = await creatorClient.create1155OnExistingContract({
            contractAddress,
            token: {
                tokenMetadataURI: `${BASE_URL}/nft-metadata/${metadataFiles[i]}`,
            },
            account: account.address,
        });

        const { request: mintRequest } = await publicClient.simulateContract(mintParams);
        const mintHash = await walletClient.writeContract(mintRequest);
        const mintReceipt = await publicClient.waitForTransactionReceipt({ hash: mintHash });

        console.log(`    TX: ${mintHash}`);
        console.log(`    Status: ${mintReceipt.status}`);
        deployInfo.tokens.push({ file: metadataFiles[i], tx: mintHash });
    }

    // Final balance
    const finalBalance = await publicClient.getBalance({ address: account.address });
    const spent = balance - finalBalance;
    console.log(`\nDone! All ${metadataFiles.length} CogCorp NFTs created on Zora.`);
    console.log(`Gas spent: ${formatEther(spent)} ETH`);
    console.log(`Remaining: ${formatEther(finalBalance)} ETH`);
    console.log(`\nView on Zora: https://zora.co/collect/zora:${contractAddress}`);

    // Save deployment info
    writeFileSync("nft-metadata/cogcorp-deployed-zora.json", JSON.stringify(deployInfo, null, 2));
    console.log("Saved deployment info to nft-metadata/cogcorp-deployed-zora.json");
}

main().catch(err => {
    console.error("Error:", err.message);
    process.exit(1);
});
