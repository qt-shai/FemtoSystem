function [M] = reverseOddsLines(M)

% Get the number of rows in the matrix
numRows = size(M, 1);

% Reverse the order of odd rows
for i = 1:2:numRows
    M(i, :) = fliplr(M(i, :));
end

