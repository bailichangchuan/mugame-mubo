let pieceManager = null;
let aiPlayer = null;

function initializeGameState(initialState) {
    gameState = JSON.parse(JSON.stringify(initialState));
    
    if (gameState.rolled_by_player === true && gameState.has_rolled === false) {
        gameState.has_rolled = true;
    }

    if (gameState.piece_types) {
        pieceManager = new AIPieceManager(gameState.piece_types);
        aiPlayer = new AIPlayer(pieceManager, 'medium');
        aiPlayer.setSide('B');
    }
}

let boardHeight = 0;
let boardWidth = 0;

function setBoardSize(height, width) {
    boardHeight = height;
    boardWidth = width;
}

function isRangedPiece(piece) {
    if (!piece) return false;
    if (gameState.piece_types?.[piece.type]?.attack_type === 'ranged') {
        return true;
    }
    return ['T', 'P'].includes(piece.type);
}

function getRangedAttackRange(piece) {
    if (!piece) return 0;
    if (gameState.piece_types?.[piece.type]?.attack_range) {
        return gameState.piece_types[piece.type].attack_range;
    }
    return 2;
}

function getRangedAttackTargets(piece, pos, gameState) {
    const [col, row] = pos;
    const targets = [];
    const board = gameState.board;
    const numRows = board.length;
    const numCols = board[0].length;
    const attackRange = getRangedAttackRange(piece);

    for (let targetRow = 0; targetRow < numRows; targetRow++) {
        for (let targetCol = 0; targetCol < numCols; targetCol++) {
            const dist = Math.abs(targetRow - row) + Math.abs(targetCol - col);
            if (dist > 0 && dist <= attackRange) {
                const target = board[targetRow][targetCol];
                if (target && target.side !== piece.side) {
                    targets.push({
                        row: targetRow,
                        col: targetCol,
                        dist: dist,
                        isRangedAttack: true
                    });
                }
            }
        }
    }
    return targets;
}

function transformCoord(viewR, viewC) {
    if (boardHeight === 0 || boardWidth === 0) {
        return { r: viewR, c: viewC };
    }
    return { r: boardHeight - 1 - viewR, c: viewC };
}

function viewToData(viewR, viewC) {
    return transformCoord(viewR, viewC);
}

function dataToView(dataR, dataC) {
    return { viewR: boardHeight - 1 - dataR, viewC: dataC };
}

function calculatePathCost(fromPos, toPos, gameState, piece) {
    const [fromCol, fromRow] = fromPos;
    const [toCol, toRow] = toPos;
    
    if (fromRow === toRow && fromCol === toCol) return { cost: 0, path: [] };
    
    const board = gameState.board;
    const numRows = board.length;
    const numCols = board[0].length;
    const terrainHeight = gameState.terrain?.height;
    const dr = [1, -1, 0, 0];
    const dc = [0, 0, 1, -1];
    
    function getHeightCost(row, col, prevRow, prevCol) {
        if (!terrainHeight) return 1;
        
        const currentHeight = terrainHeight[row]?.[col] || 0;
        
        if (prevRow === null || prevCol === null) {
            return 1;
        }
        
        const prevHeight = terrainHeight[prevRow]?.[prevCol] || 0;
        const heightDiff = currentHeight - prevHeight;
        
        if (heightDiff > 0) {
            return 1 + heightDiff;
        } else if (heightDiff < 0) {
            return Math.max(1, 1 + heightDiff);
        }
        return 1;
    }
    
    const queue = [[fromCol, fromRow, 0, [], null, null]];
    const visited = new Map();
    visited.set(`${fromCol},${fromRow}`, 0);
    
    while (queue.length > 0) {
        const [col, row, cost, path, prevCol, prevRow] = queue.shift();
        
        for (let i = 0; i < 4; i++) {
            const nextCol = col + dc[i];
            const nextRow = row + dr[i];
            
            if (nextCol < 0 || nextCol >= numCols || nextRow < 0 || nextRow >= numRows) continue;
            
            if (nextRow === toRow && nextCol === toCol) {
                const stepCost = getHeightCost(nextRow, nextCol, row, col);
                const nextCost = cost + stepCost;
                return { cost: nextCost, path: [...path, { row: nextRow, col: nextCol, heightCost: stepCost }] };
            }
            
            const target = board[nextRow][nextCol];
            if (target) continue;
            
            const stepCost = getHeightCost(nextRow, nextCol, row, col);
            const nextCost = cost + stepCost;
            
            const prevCost = visited.get(`${nextCol},${nextRow}`) || Infinity;
            
            if (nextCost < prevCost) {
                visited.set(`${nextCol},${nextRow}`, nextCost);
                queue.push([nextCol, nextRow, nextCost, [...path, { row: nextRow, col: nextCol, heightCost: stepCost }], col, row]);
            }
        }
    }
    
    return { cost: Infinity, path: [] };
}

function getMoveRange(piece, pos, stepsLeft, gameState) {
    const [col, row] = pos;
    const moveRange = [];
    const captureRange = [];
    const rangedAttacks = [];
    const moveDetails = new Map();

    if (!piece || !gameState) return { moves: [], captures: [], rangedAttacks: [], details: new Map() };

    const board = gameState.board;
    const numRows = board.length;
    const numCols = board[0].length;

    const ranged = isRangedPiece(piece);
    const rangedTargets = ranged ? getRangedAttackTargets(piece, pos, gameState) : [];

    for (let targetRow = 0; targetRow < numRows; targetRow++) {
        for (let targetCol = 0; targetCol < numCols; targetCol++) {
            if (targetRow === row && targetCol === col) continue;

            const dist = Math.abs(targetRow - row) + Math.abs(targetCol - col);
            if (dist > stepsLeft) continue;

            const toPos = [targetCol, targetRow];
            const target = board[targetRow][targetCol];

            const pathResult = calculatePathCost(pos, toPos, gameState, piece);

            if (pathResult.cost <= stepsLeft) {
                const moveInfo = {
                    row: targetRow,
                    col: targetCol,
                    cost: pathResult.cost,
                    path: pathResult.path,
                    isCapture: target && target.side !== piece.side
                };

                moveDetails.set(`${targetCol},${targetRow}`, moveInfo);

                if (target && target.side !== piece.side) {
                    captureRange.push({ row: targetRow, col: targetCol, cost: pathResult.cost });
                } else if (!target) {
                    moveRange.push({ row: targetRow, col: targetCol, cost: pathResult.cost });
                }
            }
        }
    }

    for (const rt of rangedTargets) {
        const key = `${rt.col},${rt.row}`;
        if (!moveDetails.has(key)) {
            moveDetails.set(key, {
                row: rt.row,
                col: rt.col,
                cost: 0,
                path: [],
                isCapture: true,
                isRangedAttack: true
            });
            rangedAttacks.push({ row: rt.row, col: rt.col, dist: rt.dist });
        }
    }

    return { moves: moveRange, captures: captureRange, rangedAttacks: rangedAttacks, details: moveDetails };
}

function getValidMoves(piece, pos, stepsLeft, gameState) {
    const range = getMoveRange(piece, pos, stepsLeft, gameState);
    return { moves: range.moves, captures: range.captures };
}

function getMoveInfo(row, col) {
    if (typeof moveDetailsMap !== 'undefined' && moveDetailsMap) {
        return moveDetailsMap.get(`${col},${row}`) || null;
    }
    return null;
}

function getFarthestInDirection(fromCol, fromRow, toCol, toRow) {
    const dCol = Math.sign(toCol - fromCol);
    const dRow = Math.sign(toRow - fromRow);
    
    let currentCol = fromCol;
    let currentRow = fromRow;
    let farthestCol = fromCol;
    let farthestRow = fromRow;
    let farthestDist = 0;
    
    const maxSteps = gameState.steps_left || 0;
    let stepsUsed = 0;
    
    const attacker = gameState.board[fromRow][fromCol];
    if (!attacker) return { row: fromRow, col: fromCol, dist: 0 };
    
    const behavior = pieceManager.getBehavior(attacker.type);
    if (!behavior) return { row: fromRow, col: fromCol, dist: 0 };
    
    while (stepsUsed < maxSteps) {
        const nextCol = currentCol + dCol;
        const nextRow = currentRow + dRow;
        
        if (nextCol < 0 || nextCol >= (gameState.board[0]?.length || 9) ||
            nextRow < 0 || nextRow >= gameState.board.length) break;
        
        const target = gameState.board[nextRow][nextCol];
        
        const moveResult = behavior.canMove([currentCol, currentRow], [nextCol, nextRow], gameState);
        if (!moveResult.canMove) break;
        
        const moveCost = behavior.calculateMoveCost([currentCol, currentRow], [nextCol, nextRow], gameState);
        
        currentCol = nextCol;
        currentRow = nextRow;
        farthestCol = nextCol;
        farthestRow = nextRow;
        farthestDist++;
        stepsUsed += moveCost;
    }
    
    return { row: farthestRow, col: farthestCol, dist: farthestDist };
}

function hasLineOfSight(fromPos, toPos, gameState) {
    const [fromCol, fromRow] = fromPos;
    const [toCol, toRow] = toPos;
    
    if (fromRow === toRow && fromCol === toCol) return true;
    
    const dCol = Math.sign(toCol - fromCol);
    const dRow = Math.sign(toRow - fromRow);
    
    if (dCol !== 0 && dRow !== 0) return false;
    
    let currentCol = fromCol + dCol;
    let currentRow = fromRow + dRow;
    
    while (currentCol !== toCol || currentRow !== toRow) {
        if (gameState.board[currentRow][currentCol]) return false;
        currentCol += dCol;
        currentRow += dRow;
    }
    
    return true;
}
