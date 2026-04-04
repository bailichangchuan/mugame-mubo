// ========== 战斗计算器类 ==========
class CombatCalculator {
    static calculatePower(piece, baseVal, distance, role, enemyPiece, position, terrainTypes, terrain, heightDiff, pieceTypes, board, side, k = 0.1) {
        const pType = piece.type;
        
        if (['S', 'X', 'G'].includes(pType)) {
            return CombatCalculator.calculateMeleePower(piece, baseVal, distance, role, enemyPiece, position, terrainTypes, terrain, heightDiff, pieceTypes, board, side, k);
        } else {
            return CombatCalculator.calculateRangedPower(piece, baseVal, distance, role, enemyPiece, position, terrainTypes, terrain, heightDiff, pieceTypes, board, side, k);
        }
    }

    static calculateMeleePower(piece, baseVal, distance, role, enemyPiece, position, terrainTypes, terrain, heightDiff, pieceTypes, board, side, k = 0.1) {
        let multiplier = 1.0;
        const pType = piece.type;

        if (position && board && side && pieceTypes) {
            const currentHeight = terrain?.height?.[position[1]]?.[position[0]] || 0;
            const coopRange = pieceTypes[pType]?.coop_range || 1;
            const chainMultiplier = CombatCalculator.chainAttack(board, position, pType, coopRange, role, currentHeight, pieceTypes, side, k);
            multiplier *= chainMultiplier;
        }

        if (pieceTypes?.[pType]?.base_multiplier) {
            multiplier *= pieceTypes[pType].base_multiplier;
        } else if (pType === 'X') {
            multiplier *= 1.3;
        }

        if (position && terrainTypes && terrain?.type) {
            const terrainType = terrain.type[position[1]]?.[position[0]];
            if (terrainType && terrainTypes[terrainType]) {
                multiplier *= terrainTypes[terrainType].combat_bonus || 1.0;
            }
        }

        return Math.round(baseVal * multiplier * 10) / 10;
    }

    static calculateRangedPower(piece, baseVal, distance, role, enemyPiece, position, terrainTypes, terrain, heightDiff, pieceTypes, board, side, k = 0.1) {
        let multiplier = 1.0;
        const pType = piece.type;

        if (position && board && side && pieceTypes) {
            const currentHeight = terrain?.height?.[position[1]]?.[position[0]] || 0;
            const coopRange = pieceTypes[pType]?.coop_range || 1;
            const chainMultiplier = CombatCalculator.chainAttack(board, position, pType, coopRange, role, currentHeight, pieceTypes, side, k);
            multiplier *= chainMultiplier;
        }

        if (pieceTypes?.[pType]?.base_multiplier) {
            multiplier *= pieceTypes[pType].base_multiplier;
        } else if (pType === 'X') {
            multiplier *= 1.3;
        }

        let baseMultiplier = 1.0;
        if (pieceTypes?.[pType]) {
            baseMultiplier = role === 'attacker' ? 
                (pieceTypes[pType].base_power || 1.0) : 
                (pieceTypes[pType].defense_power || 1.0);
        } else if (pType === 'T') {
            baseMultiplier = role === 'attacker' ? 1.2 : 0.8;
        } else if (pType === 'P') {
            baseMultiplier = role === 'attacker' ? 1.5 : 0.7;
        }

        if (role === 'attacker') {
            const attackMultiplier = CombatCalculator.calcRangedMultiplier(distance, baseMultiplier, heightDiff);
            multiplier *= attackMultiplier;
        } else {
            multiplier *= baseMultiplier;
        }

        if (position && terrainTypes && terrain?.type) {
            const terrainType = terrain.type[position[1]]?.[position[0]];
            if (terrainType && terrainTypes[terrainType]) {
                multiplier *= terrainTypes[terrainType].combat_bonus || 1.0;
            }
        }

        return Math.round(baseVal * multiplier * 10) / 10;
    }

    static chainAttack(board, position, pieceType, coopRange, role, currentHeight, pieceTypes, side, k = 0.1) {
        const [x, y] = position;
        const coopPieces = [];
        
        const startX = Math.max(0, x - coopRange);
        const endX = Math.min(board[0].length - 1, x + coopRange);
        const startY = Math.max(0, y - coopRange);
        const endY = Math.min(board.length - 1, y + coopRange);
        
        for (let i = startY; i <= endY; i++) {
            for (let j = startX; j <= endX; j++) {
                if (i === y && j === x) continue;
                
                const manhattanDistance = Math.abs(i - y) + Math.abs(j - x);
                if (manhattanDistance > coopRange) continue;
                
                const piece = board[i][j];
                if (piece && piece.side === side) {
                    const pieceHeight = 0;
                    const heightDiff = Math.abs(currentHeight - pieceHeight);
                    if (heightDiff <= 1) {
                        coopPieces.push(piece);
                    }
                }
            }
        }
        
        if (!coopPieces.length) {
            let basePower = 1.0;
            if (pieceTypes?.[pieceType]) {
                basePower = role === 'attacker' ? 
                    (pieceTypes[pieceType].base_power || 1.0) : 
                    (pieceTypes[pieceType].defense_power || 1.0);
            }
            return basePower;
        }
        
        let totalCoop = 0;
        const uniqueTypes = new Set();
        
        for (const piece of coopPieces) {
            const coopType = piece.type;
            uniqueTypes.add(coopType);
            if (role === 'attacker') {
                totalCoop += pieceTypes?.[coopType]?.attack_coop || 1.0;
            } else {
                totalCoop += pieceTypes?.[coopType]?.defense_coop || 1.0;
            }
        }
        
        const number = coopPieces.length;
        const T = uniqueTypes.size;
        const coopNumber = totalCoop * (1 + k * (number + T - 2));
        
        let basePower = 1.0;
        if (pieceTypes?.[pieceType]) {
            basePower = role === 'attacker' ? 
                (pieceTypes[pieceType].base_power || 1.0) : 
                (pieceTypes[pieceType].defense_power || 1.0);
        }
        
        return (basePower + coopNumber) / 2;
    }

    static calcRangedMultiplier(distance, baseMultiplier, heightDiff = 0) {
        const standardRangeStart = 2;
        const standardRangeEnd = 2 + heightDiff;
        const maxAttackRange = 3 + heightDiff;
        const heightBonus = 0.1 * heightDiff;
        
        if (distance < 1 || distance > maxAttackRange) {
            return 0.0;
        } else if (distance === 1) {
            return Math.max(0.1, baseMultiplier - 0.4 + heightBonus);
        } else if (distance >= 2 && distance <= standardRangeEnd) {
            return baseMultiplier + heightBonus;
        } else {
            return Math.max(0.1, baseMultiplier - 0.7 + heightBonus);
        }
    }
}
