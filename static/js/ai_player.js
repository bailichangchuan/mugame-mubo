/**
 * AI玩家模块 - 纯前端实现
 * 提供AI决策逻辑，用于自动控制游戏中的棋子
 */

class RoutePlanner {
    /**
     * 路线规划器
     * 为AI棋子规划从起点到目标的完整路线
     */
    constructor(boardWidth, boardHeight, terrain) {
        this.width = boardWidth;
        this.height = boardHeight;
        this.terrain = terrain;
        this.plans = {};  // 存储每个棋子的路线计划
        this.moveHistory = {};  // 记录移动历史，防止来回移动
    }

    /**
     * 为整个棋局规划协调的进攻路线（非常积极的进攻策略）
     */
    planInitialRoutes(aiPieces, enemyPieces, gameState) {
        const plans = {};

        // 找到敌方枭的位置（主要目标）
        let enemyXiaoPos = null;
        for (const enemyInfo of enemyPieces) {
            if (enemyInfo.piece.type === 'X') {
                enemyXiaoPos = enemyInfo.pos;
                break;
            }
        }

        if (!enemyXiaoPos) {
            return plans;
        }

        // 分析敌方阵型弱点
        const enemyFrontline = this._analyzeEnemyFrontline(enemyPieces);

        // 分类AI棋子
        const aiMeleePieces = [];
        const aiRangedPieces = [];
        let aiXiaoPiece = null;

        for (const pieceInfo of aiPieces) {
            const pieceType = pieceInfo.piece.type;
            if (pieceType === 'X') {
                aiXiaoPiece = pieceInfo;
            } else if (['T', 'P'].includes(pieceType)) {
                aiRangedPieces.push(pieceInfo);
            } else {
                aiMeleePieces.push(pieceInfo);
            }
        }

        // 为整个棋局规划多路进攻
        // 策略：所有棋子同时向敌方枭施压，形成包围态势

        // 1. 近战单位：直接冲锋，向敌方枭推进
        for (const pieceInfo of aiMeleePieces) {
            const fromPos = pieceInfo.pos;
            const piece = pieceInfo.piece;

            // 计算进攻路线，优先选择能威胁敌方枭的路径
            const targetPos = this._findAggressiveTarget(fromPos, enemyXiaoPos, enemyPieces, gameState, 'melee');

            if (targetPos) {
                const path = this._findPath(fromPos, targetPos, gameState);
                if (path && path.length > 0) {
                    plans[fromPos.join(',')] = path;
                }
            }
        }

        // 2. 远程单位：寻找能覆盖敌方枭的火力位置
        for (const pieceInfo of aiRangedPieces) {
            const fromPos = pieceInfo.pos;
            const piece = pieceInfo.piece;
            const pieceType = piece.type;

            // 炮兵和弓箭手寻找能攻击敌方枭的位置
            const targetPos = this._findAggressiveTarget(fromPos, enemyXiaoPos, enemyPieces, gameState, 'ranged');

            if (targetPos) {
                const path = this._findPath(fromPos, targetPos, gameState);
                if (path && path.length > 0) {
                    plans[fromPos.join(',')] = path;
                }
            }
        }

        // 3. 枭：虽然在后方，但也要有进攻意图，准备支援
        if (aiXiaoPiece) {
            const fromPos = aiXiaoPiece.pos;
            // 枭向战场中心移动，准备支援或参与围攻
            const targetPos = this._findXiaoSupportPosition(fromPos, enemyXiaoPos, aiPieces, gameState);

            if (targetPos) {
                const path = this._findPath(fromPos, targetPos, gameState);
                if (path && path.length > 0) {
                    plans[fromPos.join(',')] = path;
                }
            }
        }

        this.plans = plans;
        return plans;
    }

    /**
     * 分析敌方阵型弱点
     */
    _analyzeEnemyFrontline(enemyPieces) {
        if (!enemyPieces.length) {
            return { weakPoints: [], strongPoints: [] };
        }

        // 找出敌方阵型的薄弱点
        const positions = enemyPieces.map(info => info.pos);

        // 计算平均位置
        const avgX = positions.reduce((sum, pos) => sum + pos[0], 0) / positions.length;
        const avgY = positions.reduce((sum, pos) => sum + pos[1], 0) / positions.length;

        // 找出离平均位置最远的棋子（可能是孤立的）
        const weakPoints = [];
        const strongPoints = [];

        for (const info of enemyPieces) {
            const pos = info.pos;
            const distanceToCenter = Math.abs(pos[0] - avgX) + Math.abs(pos[1] - avgY);

            if (distanceToCenter > 2) {
                weakPoints.push(pos);
            } else {
                strongPoints.push(pos);
            }
        }

        return { weakPoints, strongPoints };
    }

    /**
     * 为棋子寻找激进的进攻目标
     */
    _findAggressiveTarget(fromPos, enemyXiaoPos, enemyPieces, gameState, pieceRole) {
        const board = gameState.board || [];
        if (!board.length) return null;

        if (pieceRole === 'melee') {
            // 近战单位：直接向敌方枭冲锋
            // 寻找能威胁敌方枭的位置
            let bestPos = null;
            let bestScore = -Infinity;

            for (let y = 0; y < this.height; y++) {
                for (let x = 0; x < this.width; x++) {
                    const pos = [x, y];

                    // 检查是否可通行
                    if (board[y][x] !== null) {
                        continue;
                    }

                    // 计算到敌方枭的距离
                    const distanceToXiao = Math.abs(x - enemyXiaoPos[0]) + Math.abs(y - enemyXiaoPos[1]);

                    // 激进策略：优先选择靠近敌方枭的位置
                    let score;
                    if (distanceToXiao <= 2) {
                        score = 100 - distanceToXiao * 20; // 越近越好
                    } else if (distanceToXiao <= 4) {
                        score = 50 - distanceToXiao * 5;
                    } else {
                        score = 10 - distanceToXiao;
                    }

                    // 考虑当前位置到目标的距离（不要太远）
                    const distanceFromCurrent = Math.abs(x - fromPos[0]) + Math.abs(y - fromPos[1]);
                    if (distanceFromCurrent > 5) {
                        score -= 20; // 太远扣分
                    }

                    // 高度优势
                    const terrain = gameState.terrain || {};
                    if (terrain.height && terrain.height[y] && terrain.height[enemyXiaoPos[1]]) {
                        const height = terrain.height[y][x];
                        const enemyHeight = terrain.height[enemyXiaoPos[1]][enemyXiaoPos[0]];
                        const heightDiff = height - enemyHeight;
                        score += heightDiff * 10;
                    }

                    if (score > bestScore) {
                        bestScore = score;
                        bestPos = pos;
                    }
                }
            }

            return bestPos;

        } else { // ranged
            // 远程单位：寻找能攻击敌方枭的位置
            let bestPos = null;
            let bestScore = -Infinity;

            for (let y = 0; y < this.height; y++) {
                for (let x = 0; x < this.width; x++) {
                    const pos = [x, y];

                    // 检查是否可通行
                    if (board[y][x] !== null) {
                        continue;
                    }

                    // 计算到敌方枭的距离
                    const distanceToXiao = Math.abs(x - enemyXiaoPos[0]) + Math.abs(y - enemyXiaoPos[1]);

                    // 远程单位最佳攻击距离是2-3格
                    let score;
                    if (distanceToXiao >= 2 && distanceToXiao <= 3) {
                        score = 100; // 最佳射击位置
                    } else if (distanceToXiao === 1) {
                        score = 60; // 太近，但还能攻击
                    } else if (distanceToXiao === 4) {
                        score = 70; // 刚好在攻击范围内
                    } else {
                        score = 10; // 太远或太近
                    }

                    // 高度优势（远程单位更需要）
                    const terrain = gameState.terrain || {};
                    if (terrain.height && terrain.height[y] && terrain.height[enemyXiaoPos[1]]) {
                        const height = terrain.height[y][x];
                        const enemyHeight = terrain.height[enemyXiaoPos[1]][enemyXiaoPos[0]];
                        const heightDiff = height - enemyHeight;
                        score += heightDiff * 15; // 高度对远程更重要
                    }

                    if (score > bestScore) {
                        bestScore = score;
                        bestPos = pos;
                    }
                }
            }

            return bestPos;
        }
    }

    /**
     * 为枭寻找支援位置
     */
    _findXiaoSupportPosition(fromPos, enemyXiaoPos, aiPieces, gameState) {
        const board = gameState.board || [];
        if (!board.length) return null;

        // 枭向战场中心移动，准备参与围攻
        // 计算战场中心（敌方枭和AI棋子之间的位置）
        const aiPositions = aiPieces.filter(info => info.piece.type !== 'X').map(info => info.pos);

        if (!aiPositions.length) return null;

        // 计算AI棋子的平均位置
        const avgX = aiPositions.reduce((sum, pos) => sum + pos[0], 0) / aiPositions.length;
        const avgY = aiPositions.reduce((sum, pos) => sum + pos[1], 0) / aiPositions.length;

        // 寻找靠近战场中心但保持安全距离的位置
        let bestPos = null;
        let bestScore = -Infinity;

        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                const pos = [x, y];

                // 检查是否可通行
                if (board[y][x] !== null) {
                    continue;
                }

                // 计算到战场中心的距离
                const distanceToCenter = Math.abs(x - avgX) + Math.abs(y - avgY);

                // 计算到敌方枭的距离（保持安全）
                const distanceToEnemy = Math.abs(x - enemyXiaoPos[0]) + Math.abs(y - enemyXiaoPos[1]);

                // 评分：靠近战场中心，但远离敌方枭
                let score;
                if (distanceToCenter <= 2) {
                    score = 80 - distanceToCenter * 10;
                } else {
                    score = 50 - distanceToCenter * 5;
                }

                // 安全距离加分
                if (distanceToEnemy >= 3) {
                    score += 20;
                } else if (distanceToEnemy >= 2) {
                    score += 10;
                } else {
                    score -= 20; // 太危险
                }

                if (score > bestScore) {
                    bestScore = score;
                    bestPos = pos;
                }
            }
        }

        return bestPos;
    }

    /**
     * 使用BFS寻找从起点到目标的最短路径
     */
    _findPath(start, goal, gameState) {
        if (start[0] === goal[0] && start[1] === goal[1]) {
            return [];
        }

        const board = gameState.board || [];
        const terrainTypes = gameState.terrain_types || {};
        const terrain = gameState.terrain || {};

        // BFS队列: [当前位置, 路径]
        const queue = [[start, [start]]];
        const visited = new Set();
        visited.add(start.join(','));

        while (queue.length > 0) {
            const [current, path] = queue.shift();

            // 检查相邻位置
            const directions = [[0, 1], [1, 0], [0, -1], [-1, 0]];
            for (const [dx, dy] of directions) {
                const nextX = current[0] + dx;
                const nextY = current[1] + dy;

                // 检查边界
                if (nextX < 0 || nextX >= this.width || nextY < 0 || nextY >= this.height) {
                    continue;
                }

                const nextPos = [nextX, nextY];
                const nextKey = nextPos.join(',');

                // 检查是否已访问
                if (visited.has(nextKey)) {
                    continue;
                }

                // 检查是否可通行
                if (terrain.type && terrain.type[nextY] && terrain.type[nextY][nextX]) {
                    const terrainType = terrain.type[nextY][nextX];
                    const terrainConfig = terrainTypes[terrainType];
                    if (terrainConfig && terrainConfig.passability === 0) {
                        continue;
                    }
                }

                // 检查是否有敌方棋子（目标位置除外）
                const isGoal = nextX === goal[0] && nextY === goal[1];
                if (!isGoal && board && board[nextY] && board[nextY][nextX]) {
                    const piece = board[nextY][nextX];
                    if (piece.side !== gameState.ai_side) {
                        // 是敌方棋子，不能穿过
                        continue;
                    }
                }

                const newPath = [...path, nextPos];

                // 到达目标
                if (isGoal) {
                    return newPath.slice(1); // 返回不含起点的路径
                }

                visited.add(nextKey);
                queue.push([nextPos, newPath]);
            }
        }

        return []; // 没有找到路径
    }

    /**
     * 为枭寻找安全位置
     */
    _findSafePosition(currentPos, enemyPieces, gameState) {
        const board = gameState.board || [];
        if (!board.length) return currentPos;

        // 寻找距离敌方最远的可通行位置
        let bestPos = currentPos;
        let maxMinDistance = -1;

        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                const pos = [x, y];

                // 跳过当前位置
                if (pos[0] === currentPos[0] && pos[1] === currentPos[1]) {
                    continue;
                }

                // 检查是否可通行
                if (board[y][x] !== null) {
                    continue;
                }

                // 计算到最近敌方的距离
                let minDistance = Infinity;
                for (const enemyInfo of enemyPieces) {
                    const enemyPos = enemyInfo.pos;
                    const distance = Math.abs(x - enemyPos[0]) + Math.abs(y - enemyPos[1]);
                    minDistance = Math.min(minDistance, distance);
                }

                // 选择距离敌方最远的位置
                if (minDistance > maxMinDistance) {
                    maxMinDistance = minDistance;
                    bestPos = pos;
                }
            }
        }

        return bestPos;
    }

    /**
     * 为远程单位寻找有利射击位置
     */
    _findRangedPosition(currentPos, targetPos, gameState) {
        if (!targetPos) return currentPos;

        const board = gameState.board || [];
        if (!board.length) return currentPos;

        let bestPos = currentPos;
        let bestScore = -Infinity;

        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                const pos = [x, y];

                // 检查是否可通行
                if (board[y][x] !== null) {
                    continue;
                }

                // 计算到目标的距离
                const distance = Math.abs(x - targetPos[0]) + Math.abs(y - targetPos[1]);

                // 最佳距离是2-3格
                let score;
                if (distance >= 2 && distance <= 3) {
                    score = 100 - distance; // 距离越近越好，但在最佳范围内
                } else if (distance < 2) {
                    score = 50 - distance * 10; // 太近，扣分
                } else {
                    score = 10 - distance; // 太远，大幅扣分
                }

                // 高度优势加分
                const terrain = gameState.terrain || {};
                if (terrain.height && terrain.height[y] && terrain.height[targetPos[1]]) {
                    const currentHeight = terrain.height[y][x];
                    const targetHeight = terrain.height[targetPos[1]][targetPos[0]];
                    const heightDiff = currentHeight - targetHeight;
                    score += heightDiff * 20; // 高度优势加分
                }

                if (score > bestScore) {
                    bestScore = score;
                    bestPos = pos;
                }
            }
        }

        return bestPos;
    }

    /**
     * 寻找最近的敌方棋子
     */
    _findNearestEnemy(currentPos, enemyPieces) {
        if (!enemyPieces.length) return currentPos;

        let nearestPos = enemyPieces[0].pos;
        let minDistance = Infinity;

        for (const enemyInfo of enemyPieces) {
            const enemyPos = enemyInfo.pos;
            const distance = Math.abs(currentPos[0] - enemyPos[0]) + Math.abs(currentPos[1] - enemyPos[1]);
            if (distance < minDistance) {
                minDistance = distance;
                nearestPos = enemyPos;
            }
        }

        return nearestPos;
    }

    /**
     * 检测是否是来回移动
     */
    isBackAndForth(piecePos, newPos) {
        const key = piecePos.join(',');
        if (!this.moveHistory[key]) {
            return false;
        }

        const history = this.moveHistory[key];

        // 检查最近3次移动
        if (history.length >= 3) {
            // 检查是否是 A -> B -> A 模式
            const lastMove = history[history.length - 1];
            const secondLastMove = history[history.length - 2];
            
            if (lastMove[0] === newPos[0] && lastMove[1] === newPos[1] &&
                secondLastMove[0] === piecePos[0] && secondLastMove[1] === piecePos[1]) {
                return true;
            }
        }

        return false;
    }

    /**
     * 更新移动历史
     */
    updateMoveHistory(piecePos, newPos) {
        const key = piecePos.join(',');
        if (!this.moveHistory[key]) {
            this.moveHistory[key] = [];
        }

        this.moveHistory[key].push(newPos);

        // 只保留最近5次移动
        if (this.moveHistory[key].length > 5) {
            this.moveHistory[key].shift();
        }
    }

    /**
     * 获取棋子的下一个移动位置
     */
    getNextMove(piecePos, aiSide = 'B', isProtecting = false) {
        const key = piecePos.join(',');
        if (!this.plans[key]) {
            return null;
        }

        const plan = this.plans[key];

        if (!plan || plan.length === 0) {
            return null;
        }

        // 返回计划中的下一个位置
        const nextPos = plan[0];

        // 禁止原路返回：如果检测到原路返回（A->B->A），返回null
        if (this.isBackAndForth(piecePos, nextPos)) {
            return null;
        }

        // 如果正在保护棋子，允许后退
        if (isProtecting) {
            return nextPos;
        }

        // 禁止往回走：像中国象棋的兵一样，永远不能往回走
        // 黑方（B）在下方，向上走是前进，向下走是后退
        // 红方（R）在上方，向下走是前进，向上走是后退
        const currentY = piecePos[1];
        const nextY = nextPos[1];

        if (aiSide === 'B') {
            // 黑方：y坐标减小是前进，y坐标增大是后退
            if (nextY > currentY) {
                return null;  // 禁止往回走
            }
        } else {  // aiSide === 'R'
            // 红方：y坐标增大是前进，y坐标减小是后退
            if (nextY < currentY) {
                return null;  // 禁止往回走
            }
        }

        return nextPos;
    }

    /**
     * 调整计划（只在必要时重新规划）
     */
    adjustPlan(piecePos, playerMove, gameState, isBlocked = false, pieceLost = false) {
        const key = piecePos.join(',');
        if (!this.plans[key]) {
            return [];
        }

        const currentPlan = this.plans[key];

        // 只有在以下情况才重新规划路线：
        // 1. 棋子被阻挡无法前进
        // 2. 有棋子阵亡
        // 3. 敌方棋子移动到了计划路径上（阻挡）

        // 如果被阻挡或有棋子阵亡，需要重新规划
        if (isBlocked || pieceLost) {
            const analysis = this._analyzeBoard(gameState);
            const enemyPieces = analysis.enemyPieces;

            // 找到新的目标
            let enemyXiaoPos = null;
            for (const enemyInfo of enemyPieces) {
                if (enemyInfo.piece.type === 'X') {
                    enemyXiaoPos = enemyInfo.pos;
                    break;
                }
            }

            if (enemyXiaoPos) {
                const newPath = this._findPath(piecePos, enemyXiaoPos, gameState);
                this.plans[key] = newPath;
                return newPath;
            }
        }

        // 如果玩家移动到了我们的计划路径上（阻挡），需要重新规划
        if (playerMove) {
            const [playerFrom, playerTo] = playerMove;

            // 检查玩家是否移动到了我们的计划路径上
            if (currentPlan.some(pos => pos[0] === playerTo[0] && pos[1] === playerTo[1])) {
                const analysis = this._analyzeBoard(gameState);
                const enemyPieces = analysis.enemyPieces;

                // 找到新的目标
                let enemyXiaoPos = null;
                for (const enemyInfo of enemyPieces) {
                    if (enemyInfo.piece.type === 'X') {
                        enemyXiaoPos = enemyInfo.pos;
                        break;
                    }
                }

                if (enemyXiaoPos) {
                    const newPath = this._findPath(piecePos, enemyXiaoPos, gameState);
                    this.plans[key] = newPath;
                    return newPath;
                }
            }
        }

        // 其他情况保持原计划不变
        return currentPlan;
    }

    /**
     * 移除已完成的移动
     */
    removeCompletedMove(piecePos, movedTo) {
        const key = piecePos.join(',');
        if (this.plans[key]) {
            const plan = this.plans[key];
            if (plan && plan.length > 0 && plan[0][0] === movedTo[0] && plan[0][1] === movedTo[1]) {
                // 移除已完成的移动
                this.plans[key] = plan.slice(1);

                // 更新计划的键
                if (this.plans[key].length > 0) {
                    const newKey = movedTo.join(',');
                    this.plans[newKey] = this.plans[key];
                    delete this.plans[key];
                }
            }
        }
    }
}

class AIPieceManager {
    /**
     * 棋子管理器
     */
    constructor(pieceTypes) {
        this.pieceTypes = pieceTypes;
        this.behaviors = {};
        this._initializeBehaviors();
    }

    _initializeBehaviors() {
        for (const [pieceType, config] of Object.entries(this.pieceTypes)) {
            config.type = pieceType;
            this.behaviors[pieceType] = this._createBehavior(config);
        }
    }

    _createBehavior(pieceConfig) {
        const pieceType = pieceConfig.type;
        let behaviorType = pieceConfig.behavior_type;

        if (!behaviorType) {
            if (['S', 'X', 'G'].includes(pieceType)) {
                behaviorType = 'melee';
            } else if (pieceType === 'T') {
                behaviorType = 'ranged';
            } else if (pieceType === 'P') {
                behaviorType = 'cannon';
            } else {
                behaviorType = 'melee';
            }
        }

        if (behaviorType === 'ranged') {
            return new RangedPieceBehavior(pieceConfig);
        } else if (behaviorType === 'cannon') {
            return new CannonPieceBehavior(pieceConfig);
        } else {
            return new MeleePieceBehavior(pieceConfig);
        }
    }

    getPieceBehavior(pieceType) {
        return this.behaviors[pieceType];
    }

    getPieceConfig(pieceType) {
        return this.pieceTypes[pieceType];
    }

    canMove(piece, fromPos, toPos, gameState) {
        const behavior = this.getPieceBehavior(piece.type);
        if (!behavior) return { canMove: false, error: `未知棋子类型: ${piece.type}` };
        return behavior.canMove(fromPos, toPos, gameState);
    }

    calculateMoveCost(piece, fromPos, toPos, gameState) {
        const behavior = this.getPieceBehavior(piece.type);
        if (!behavior) return 1;
        return behavior.calculateMoveCost(fromPos, toPos, gameState);
    }

    canAttack(piece, fromPos, toPos, gameState) {
        const behavior = this.getPieceBehavior(piece.type);
        if (!behavior) return { canAttack: false, error: `未知棋子类型: ${piece.type}` };
        return behavior.canAttack(fromPos, toPos, gameState);
    }

    calculateAttackPower(piece, attackValue, distance, heightDiff, gameState) {
        const behavior = this.getPieceBehavior(piece.type);
        if (!behavior) return attackValue;
        return behavior.calculateAttackPower(attackValue, distance, heightDiff, gameState);
    }
}

class MeleePieceBehavior {
    constructor(pieceConfig) {
        this.config = pieceConfig;
        this.pieceType = pieceConfig.type;
    }

    canMove(fromPos, toPos, gameState) {
        const terrain = gameState.terrain || {};
        const terrainTypes = gameState.terrain_types || {};
        
        if (terrain.type) {
            const toRow = toPos[1];
            const toCol = toPos[0];
            if (toRow >= 0 && toRow < terrain.type.length && toCol >= 0 && toCol < terrain.type[toRow].length) {
                const terrainType = terrain.type[toRow][toCol];
                if (terrainTypes[terrainType] && terrainTypes[terrainType].passability === 0) {
                    return { canMove: false, error: "该地形不可站立" };
                }
            }
        }

        return { canMove: true, error: null };
    }

    calculateMoveCost(fromPos, toPos, gameState) {
        let moveCost = 1;
        
        const terrain = gameState.terrain || {};
        const terrainTypes = gameState.terrain_types || {};
        
        if (terrain.type) {
            const toCol = toPos[0];
            const toRow = toPos[1];
            if (toRow >= 0 && toRow < terrain.type.length && toCol >= 0 && toCol < terrain.type[toRow].length) {
                const terrainType = terrain.type[toRow][toCol];
                if (terrainTypes[terrainType]) {
                    moveCost = terrainTypes[terrainType].move_cost || 1;
                }
            }
        }

        let heightCost = 0;
        if (terrain.height) {
            const fromCol = fromPos[0];
            const fromRow = fromPos[1];
            const toCol = toPos[0];
            const toRow = toPos[1];
            
            if (fromRow >= 0 && fromRow < terrain.height.length && fromCol >= 0 && fromCol < terrain.height[fromRow].length &&
                toRow >= 0 && toRow < terrain.height.length && toCol >= 0 && toCol < terrain.height[toRow].length) {
                const fromHeight = terrain.height[fromRow][fromCol];
                const toHeight = terrain.height[toRow][toCol];
                const heightDiff = toHeight - fromHeight;
                heightCost = Math.max(0, heightDiff);
            }
        }

        return moveCost + heightCost;
    }

    canAttack(fromPos, toPos, gameState) {
        const distance = Math.abs(fromPos[0] - toPos[0]) + Math.abs(fromPos[1] - toPos[1]);
        
        if (distance !== 1) {
            return { canAttack: false, error: "近战棋子只能攻击相邻格子" };
        }

        return { canAttack: true, error: null };
    }

    calculateAttackPower(attackValue, distance, heightDiff, gameState) {
        const baseMultiplier = this.config.base_power || 1.0;
        const heightBonus = 0.1 * Math.max(0, heightDiff);
        return attackValue * (baseMultiplier + heightBonus);
    }
}

class RangedPieceBehavior {
    constructor(pieceConfig) {
        this.config = pieceConfig;
        this.pieceType = pieceConfig.type;
    }

    canMove(fromPos, toPos, gameState) {
        const terrain = gameState.terrain || {};
        const terrainTypes = gameState.terrain_types || {};
        
        if (terrain.type) {
            const toRow = toPos[1];
            const toCol = toPos[0];
            if (toRow >= 0 && toRow < terrain.type.length && toCol >= 0 && toCol < terrain.type[toRow].length) {
                const terrainType = terrain.type[toRow][toCol];
                if (terrainTypes[terrainType] && terrainTypes[terrainType].passability === 0) {
                    return { canMove: false, error: "该地形不可站立" };
                }
            }
        }

        return { canMove: true, error: null };
    }

    calculateMoveCost(fromPos, toPos, gameState) {
        let moveCost = 1;
        
        const terrain = gameState.terrain || {};
        const terrainTypes = gameState.terrain_types || {};
        
        if (terrain.type) {
            const toCol = toPos[0];
            const toRow = toPos[1];
            if (toRow >= 0 && toRow < terrain.type.length && toCol >= 0 && toCol < terrain.type[toRow].length) {
                const terrainType = terrain.type[toRow][toCol];
                if (terrainTypes[terrainType]) {
                    moveCost = terrainTypes[terrainType].move_cost || 1;
                }
            }
        }

        let heightCost = 0;
        if (terrain.height) {
            const fromCol = fromPos[0];
            const fromRow = fromPos[1];
            const toCol = toPos[0];
            const toRow = toPos[1];
            
            if (fromRow >= 0 && fromRow < terrain.height.length && fromCol >= 0 && fromCol < terrain.height[fromRow].length &&
                toRow >= 0 && toRow < terrain.height.length && toCol >= 0 && toCol < terrain.height[toRow].length) {
                const fromHeight = terrain.height[fromRow][fromCol];
                const toHeight = terrain.height[toRow][toCol];
                const heightDiff = toHeight - fromHeight;
                heightCost = Math.max(0, heightDiff);
            }
        }

        return moveCost + heightCost;
    }

    canAttack(fromPos, toPos, gameState) {
        const distance = Math.abs(fromPos[0] - toPos[0]) + Math.abs(fromPos[1] - toPos[1]);
        
        if (fromPos[0] !== toPos[0] && fromPos[1] !== toPos[1]) {
            return { canAttack: false, error: "远程攻击只能直线攻击" };
        }

        let maxRange = this.config.combat_range || 3;
        
        const terrain = gameState.terrain || {};
        if (terrain.height) {
            const [fromY, fromX] = fromPos;
            const [toY, toX] = toPos;
            
            if (fromY >= 0 && fromY < terrain.height.length && fromX >= 0 && fromX < terrain.height[fromY].length &&
                toY >= 0 && toY < terrain.height.length && toX >= 0 && toX < terrain.height[toY].length) {
                const fromHeight = terrain.height[fromY][fromX];
                const toHeight = terrain.height[toY][toX];
                const heightDiff = fromHeight - toHeight;
                maxRange += heightDiff;
            }
        }

        maxRange = Math.max(1, maxRange);
        
        if (distance < 1 || distance > maxRange) {
            return { canAttack: false, error: `攻击距离超出范围 (1-${maxRange})` };
        }

        const board = gameState.board || [];
        if (this._isPathBlocked(board, fromPos, toPos)) {
            return { canAttack: false, error: "路径上有阻挡，无法攻击" };
        }

        return { canAttack: true, error: null };
    }

    calculateAttackPower(attackValue, distance, heightDiff, gameState) {
        const baseMultiplier = this.config.base_power || 1.0;
        const standardRangeStart = 2;
        const standardRangeEnd = 2 + Math.max(0, heightDiff);
        const heightBonus = 0.1 * Math.max(0, heightDiff);
        
        let attackMultiplier;
        if (distance === 1) {
            attackMultiplier = baseMultiplier - 0.4 + heightBonus;
        } else if (distance >= 2 && distance <= standardRangeEnd) {
            attackMultiplier = baseMultiplier + heightBonus;
        } else {
            attackMultiplier = baseMultiplier - 0.7 + heightBonus;
        }

        attackMultiplier = Math.max(0.1, attackMultiplier);
        return attackValue * attackMultiplier;
    }

    _isPathBlocked(board, fromPos, toPos) {
        const [fromY, fromX] = fromPos;
        const [toY, toX] = toPos;

        if (fromY === toY) {
            const startX = Math.min(fromX, toX) + 1;
            const endX = Math.max(fromX, toX);
            for (let x = startX; x < endX; x++) {
                if (board[fromY][x] !== null) return true;
            }
        } else if (fromX === toX) {
            const startY = Math.min(fromY, toY) + 1;
            const endY = Math.max(fromY, toY);
            for (let y = startY; y < endY; y++) {
                if (board[y][fromX] !== null) return true;
            }
        }

        return false;
    }
}

class CannonPieceBehavior extends RangedPieceBehavior {
    constructor(pieceConfig) {
        super(pieceConfig);
    }

    canMove(fromPos, toPos, gameState) {
        const terrain = gameState.terrain || {};
        const terrainTypes = gameState.terrain_types || {};
        
        if (terrain.type) {
            const toRow = toPos[1];
            const toCol = toPos[0];
            if (toRow >= 0 && toRow < terrain.type.length && toCol >= 0 && toCol < terrain.type[toRow].length) {
                const terrainType = terrain.type[toRow][toCol];
                if (terrainTypes[terrainType] && terrainTypes[terrainType].passability === 0) {
                    return { canMove: false, error: "该地形不可站立" };
                }
            }
        }

        return { canMove: true, error: null };
    }

    calculateMoveCost(fromPos, toPos, gameState) {
        let moveCost = 1;
        
        const terrain = gameState.terrain || {};
        const terrainTypes = gameState.terrain_types || {};
        
        if (terrain.type) {
            const toCol = toPos[0];
            const toRow = toPos[1];
            if (toRow >= 0 && toRow < terrain.type.length && toCol >= 0 && toCol < terrain.type[toRow].length) {
                const terrainType = terrain.type[toRow][toCol];
                if (terrainTypes[terrainType]) {
                    moveCost = terrainTypes[terrainType].move_cost || 1;
                }
            }
        }

        moveCost *= 2;

        let heightCost = 0;
        if (terrain.height) {
            const fromCol = fromPos[0];
            const fromRow = fromPos[1];
            const toCol = toPos[0];
            const toRow = toPos[1];
            
            if (fromRow >= 0 && fromRow < terrain.height.length && fromCol >= 0 && fromCol < terrain.height[fromRow].length &&
                toRow >= 0 && toRow < terrain.height.length && toCol >= 0 && toCol < terrain.height[toRow].length) {
                const fromHeight = terrain.height[fromRow][fromCol];
                const toHeight = terrain.height[toRow][toCol];
                const heightDiff = toHeight - fromHeight;
                heightCost = Math.max(0, heightDiff);
            }
        }

        return moveCost + heightCost;
    }

    canAttack(fromPos, toPos, gameState) {
        const currentPlayerId = gameState.turn;
        if (gameState.has_used_cannon && gameState.has_used_cannon[String(currentPlayerId)]) {
            return { canAttack: false, error: "炮一回合只能使用一次攻击" };
        }

        return super.canAttack(fromPos, toPos, gameState);
    }

    calculateAttackPower(attackValue, distance, heightDiff, gameState) {
        const baseMultiplier = this.config.base_power || 1.5;
        const heightBonus = 0.1 * Math.max(0, heightDiff);
        
        let attackMultiplier;
        if (distance === 1) {
            attackMultiplier = baseMultiplier - 0.4 + heightBonus;
        } else {
            attackMultiplier = baseMultiplier + heightBonus;
        }

        return attackValue * attackMultiplier;
    }
}

class AIPlayer {
    /**
     * AI玩家类，负责分析游戏状态并做出决策
     */
    constructor(pieceManager, difficulty = 'medium') {
        this.pieceManager = pieceManager;
        this.difficulty = difficulty;
        this.aiSide = 'B';
        this.routePlanner = null;  // 路线规划器
    }

    setSide(side) {
        this.aiSide = side;
    }

    /**
     * 初始化路线规划器
     */
    initializeRoutePlanner(gameState) {
        const board = gameState.board || [];
        if (!board.length) return;

        const height = board.length;
        const width = board[0].length;
        const terrain = gameState.terrain || {};

        this.routePlanner = new RoutePlanner(width, height, terrain);

        // 分析棋盘
        const analysis = this.analyzeBoard(gameState);
        const aiPieces = analysis.aiPieces;
        const enemyPieces = analysis.enemyPieces;

        // 规划初始路线
        this.routePlanner.planInitialRoutes(aiPieces, enemyPieces, gameState);
    }

    analyzeBoard(gameState) {
        const board = gameState.board || [];
        if (!board.length) {
            return { aiPieces: [], enemyPieces: [], emptySpaces: [] };
        }

        const aiPieces = [];
        const enemyPieces = [];
        const emptySpaces = [];

        for (let y = 0; y < board.length; y++) {
            for (let x = 0; x < board[y].length; x++) {
                const piece = board[y][x];
                if (piece) {
                    if (piece.side === this.aiSide) {
                        aiPieces.push({ pos: [x, y], piece: piece });
                    } else {
                        enemyPieces.push({ pos: [x, y], piece: piece });
                    }
                } else {
                    emptySpaces.push([x, y]);
                }
            }
        }

        return { aiPieces, enemyPieces, emptySpaces };
    }

    isXiaoThreatened(gameState) {
        const { aiPieces, enemyPieces } = this.analyzeBoard(gameState);

        for (const aiInfo of aiPieces) {
            if (aiInfo.piece.type === 'X') {
                const [xiaoX, xiaoY] = aiInfo.pos;

                for (const enemyInfo of enemyPieces) {
                    const [enemyX, enemyY] = enemyInfo.pos;
                    const enemyConfig = this.pieceManager.getPieceConfig(enemyInfo.piece.type);
                    if (enemyConfig) {
                        const attackRange = enemyConfig.attack_range || 1;
                        const dist = Math.abs(enemyX - xiaoX) + Math.abs(enemyY - xiaoY);
                        if (dist <= attackRange + 1) {
                            return { threatened: true, xiaoPos: aiInfo.pos };
                        }
                    }
                }
            }
        }
        return { threatened: false, xiaoPos: null };
    }

    evaluateMove(piece, fromPos, toPos, gameState) {
        let score = 0.0;

        const moveResult = this.pieceManager.canMove(piece, fromPos, toPos, gameState);
        if (!moveResult.canMove) {
            return -1000.0;
        }

        const board = gameState.board || [];
        const attackResult = this.pieceManager.canAttack(piece, fromPos, toPos, gameState);
        if (attackResult.canAttack) {
            score += 50.0;

            const target = board[toPos[1]][toPos[0]];
            if (target && target.side !== this.aiSide) {
                score += 100.0;
                if (target.type === 'X') {
                    score += 1000.0;
                }
            }
        }

        if (piece.side === this.aiSide && piece.type === 'X') {
            const xiaoThreat = this.isXiaoThreatened(gameState);
            if (xiaoThreat.threatened) {
                const distToXiao = Math.abs(fromPos[0] - xiaoThreat.xiaoPos[0]) + Math.abs(fromPos[1] - xiaoThreat.xiaoPos[1]);
                if (distToXiao === 1) {
                    score += 200.0;
                }
            }
        }

        if (this.difficulty === 'easy') {
            score *= 0.5;
        } else if (this.difficulty === 'hard') {
            score *= 1.5;
        }

        score += Math.random() * 20.0 - 10.0;
        return score;
    }

    getBestMove(gameState) {
        const analysis = this.analyzeBoard(gameState);
        const aiPieces = analysis.aiPieces;

        if (!aiPieces.length) {
            return null;
        }

        // 如果路线规划器未初始化，初始化它
        if (!this.routePlanner) {
            this.initializeRoutePlanner(gameState);
        }

        // 检查AI枭是否被威胁
        const xiaoThreat = this.isXiaoThreatened(gameState);
        let aiXiaoPos = null;
        for (const aiInfo of aiPieces) {
            if (aiInfo.piece.type === 'X') {
                aiXiaoPos = aiInfo.pos;
                break;
            }
        }

        let bestMove = null;
        let bestScore = -Infinity;

        // 如果AI枭被威胁，优先寻找保护/逃跑/支援移动
        if (xiaoThreat.threatened && aiXiaoPos) {
            for (const pieceInfo of aiPieces) {
                const piece = pieceInfo.piece;
                if (piece.type === 'X') continue;

                const pieceConfig = this.pieceManager.getPieceConfig(piece.type);
                const moveRange = pieceConfig ? (pieceConfig.move_range || 1) : 1;
                const possibleMoves = this._generatePossibleMoves(pieceInfo.pos, moveRange, gameState);

                for (const toPos of possibleMoves) {
                    const distToXiao = Math.abs(toPos[0] - aiXiaoPos[0]) + Math.abs(toPos[1] - aiXiaoPos[1]);
                    if (distToXiao <= 2) {
                        const score = 800.0 - distToXiao * 100.0;
                        if (score > bestScore) {
                            bestScore = score;
                            bestMove = {
                                fromPos: pieceInfo.pos,
                                toPos: toPos,
                                piece: piece,
                                score: score
                            };
                        }
                    }
                }
            }
        }

        for (const pieceInfo of aiPieces) {
            const fromPos = pieceInfo.pos;
            const piece = pieceInfo.piece;

            // 优先使用路线规划器的建议
            if (this.routePlanner) {
                const nextPos = this.routePlanner.getNextMove(fromPos);

                if (nextPos) {
                    // 检查是否可以移动到计划位置
                    const moveResult = this.pieceManager.canMove(piece, fromPos, nextPos, gameState);

                    if (moveResult.canMove) {
                        // 检查是否是攻击移动
                        const board = gameState.board || [];
                        const target = board[nextPos[1]][nextPos[0]];

                        let score = 100.0;  // 路线规划的移动优先

                        // 如果可以攻击敌方枭，大幅加分
                        if (target && target.side !== this.aiSide) {
                            if (target.type === 'X') {
                                score += 1000.0;
                            } else {
                                score += 200.0;
                            }
                        }

                        // 检查是否是来回移动
                        if (this.routePlanner.isBackAndForth(fromPos, nextPos)) {
                            score -= 500.0;  // 大幅扣分
                        }

                        if (score > bestScore) {
                            bestScore = score;
                            bestMove = {
                                fromPos: fromPos,
                                toPos: nextPos,
                                piece: piece,
                                score: score
                            };
                            continue;
                        }
                    }
                }
            }

            // 如果路线规划器没有建议，使用传统方法
            const pieceConfig = this.pieceManager.getPieceConfig(piece.type);
            const moveRange = pieceConfig ? (pieceConfig.move_range || 1) : 1;

            const possibleMoves = this._generatePossibleMoves(fromPos, moveRange, gameState);

            for (const toPos of possibleMoves) {
                // 跳过路线规划器已建议的位置（已处理）
                if (this.routePlanner && this.routePlanner.getNextMove(fromPos) &&
                    this.routePlanner.getNextMove(fromPos)[0] === toPos[0] &&
                    this.routePlanner.getNextMove(fromPos)[1] === toPos[1]) {
                    continue;
                }

                const score = this.evaluateMove(piece, fromPos, toPos, gameState);

                // 检查是否是来回移动
                if (this.routePlanner && this.routePlanner.isBackAndForth(fromPos, toPos)) {
                    score -= 500.0;  // 大幅扣分
                }

                if (score > bestScore) {
                    bestScore = score;
                    bestMove = {
                        fromPos: fromPos,
                        toPos: toPos,
                        piece: piece,
                        score: score
                    };
                }
            }
        }

        return bestMove;
    }

    _generatePossibleMoves(fromPos, moveRange, gameState) {
        const board = gameState.board || [];
        if (!board.length) return [];

        const height = board.length;
        const width = board[0].length;
        const [x, y] = fromPos;
        const possibleMoves = [];

        for (let dy = -moveRange; dy <= moveRange; dy++) {
            for (let dx = -moveRange; dx <= moveRange; dx++) {
                if (dx === 0 && dy === 0) continue;

                const distance = Math.abs(dx) + Math.abs(dy);
                if (distance > moveRange) continue;

                const toX = x + dx;
                const toY = y + dy;

                if (toX >= 0 && toX < width && toY >= 0 && toY < height) {
                    possibleMoves.push([toX, toY]);
                }
            }
        }

        return possibleMoves;
    }

    decideCombatAction(combatState) {
        return {
            action: 'roll',
            message: 'AI掷采'
        };
    }

    decideCardUsage(gameState) {
        const cards = gameState.cards ? (gameState.cards[String(this.aiSide)] || {}) : {};
        
        if (!Object.keys(cards).length) {
            return null;
        }

        if (Math.random() < 0.3) {
            const availableCards = Object.entries(cards)
                .filter(([cardType, count]) => count > 0)
                .map(([cardType]) => cardType);
            
            if (availableCards.length) {
                return availableCards[Math.floor(Math.random() * availableCards.length)];
            }
        }

        return null;
    }
}

// 导出供HTML使用
window.AIPieceManager = AIPieceManager;
window.AIPlayer = AIPlayer;