#include <iostream>
#include <fstream>
#include <vector>
#include <cmath>
#include <map>
#include <set>
#include <filesystem>
#include <boost/math/distributions/students_t.hpp>
#include <limits>
using namespace std;
using namespace boost::math;
namespace fs = filesystem;
typedef long long ll;
typedef pair<ll, ll> pll;
#define pub push_back
#define mp make_pair
#define pob pop_back
#define X first
#define Y second
const ll INF = 0x3f3f3f3f3f3f3f3f;

// Compile with:
// g++ merge.cpp -I/opt/homebrew/include -L/opt/homebrew/lib -lboost_math_c99

// Struct to store pupil data
struct PupilData {
    double luminance;
    double avgSize;
    int count;
    double stdDev;
};

// Function to read luminance-pupil mapping for a given index (separately for left & right)
pair<map<double, PupilData>, map<double, PupilData>> readLuminanceMapping(const string &index, const string &folderPath) {
    map<double, PupilData> leftMapping, rightMapping;
    fs::path filePath = fs::path(folderPath) / (index + "_luminance_mapping.txt");

    ifstream inFile(filePath);
    if (!inFile) {
        return {leftMapping, rightMapping}; // Return empty maps (indicates missing data)
    }

    string header;
    getline(inFile, header); // Skip header

    double luminance, avgLeft, leftCount, leftStd, avgRight, rightCount, rightStd;
    while (inFile >> luminance >> avgLeft >> leftCount >> leftStd >> avgRight >> rightCount >> rightStd) {
        leftMapping[luminance] = {luminance, avgLeft, (int)leftCount, leftStd};
        rightMapping[luminance] = {luminance, avgRight, (int)rightCount, rightStd};
    }

    inFile.close();
    return {leftMapping, rightMapping};
}

// Function to read pupil data from file (left or right) - Extracting AFTER data
map<string, PupilData> readPupilData(const string &filename) {
    map<string, PupilData> data;
    ifstream inFile(filename);

    if (!inFile) {
        cerr << "Error: Could not open file " << filename << endl;
        return data;
    }

    string index;
    double lumBefore, pupilBefore, beforeCount, beforeStdDev, lumAfter, pupilAfter, afterCount, afterStdDev;
    while (inFile >> index >> lumBefore >> pupilBefore >> beforeCount >> beforeStdDev >> lumAfter >> pupilAfter >> afterCount >> afterStdDev) {
        data[index] = {lumAfter, pupilAfter, (int)afterCount, afterStdDev}; // Storing AFTER values
    }

    inFile.close();
    return data;
}

// Function to find the closest luminance match in mapping
PupilData getClosestLuminanceMatch(const map<double, PupilData> &mapping, double targetLum) {
    if (mapping.empty()) return {-1, -1, -1, -1}; // Return invalid data

    auto it = mapping.lower_bound(targetLum);
    if (it == mapping.end()) return prev(it)->second;
    if (it == mapping.begin()) return it->second;

    auto lower = prev(it);
    return (abs(lower->first - targetLum) < abs(it->first - targetLum)) ? lower->second : it->second;
}

// Function to perform two-sample t-test
double computeTTest(double mean1, double std1, int n1, double mean2, double std2, int n2) {
    if (n1 < 2 || n2 < 2) return -1.0; // Not enough data for t-test

    double pooledVar = ((pow(std1, 2) / n1) + (pow(std2, 2) / n2));
    if (pooledVar == 0) return -1.0; // Avoid division by zero

    double tScore = (mean1 - mean2) / sqrt(pooledVar);
    int df = min(n1, n2) - 1; // Degrees of freedom
    students_t dist(df);
    return 2 * (1 - cdf(dist, abs(tScore))); // Two-tailed test
}

int main() {
    string calibrationFolder = "output_mappings";

    // Read pupil data (AFTER data only)
    map<string, PupilData> leftPupilData = readPupilData("leftpupil.txt");
    map<string, PupilData> rightPupilData = readPupilData("rightpupil.txt");

    if (leftPupilData.empty() || rightPupilData.empty()) {
        cerr << "Error: One or both pupil data files are empty or could not be read.\n";
        return 1;
    }

    double alpha;
    cout << "\nEnter significance level: ";
    cin >> alpha;

    cout << "\nIndex\tLeft P-Value\tLeft Conclusion\tRight P-Value\tRight Conclusion\n";

    set<string> indices;
    for (const auto &item : leftPupilData) indices.insert(item.first);
    for (const auto &item : rightPupilData) indices.insert(item.first);

    int totalLeft = 0, totalRight = 0;
    int leftPass = 0, rightPass = 0;
    int missingLuminanceMappingCount = 0, missingPupilDataCount = 0;

    for (const string &index : indices) {
        // Read luminance mapping for the current index
        auto [leftLuminanceMapping, rightLuminanceMapping] = readLuminanceMapping(index, calibrationFolder);

        if (leftLuminanceMapping.empty() || rightLuminanceMapping.empty()) {
            missingLuminanceMappingCount++;
            cout << index << "\tMISSING\tMISSING\tMISSING\tMISSING\n";
            continue;
        }

        // Get actual pupil data
        if (leftPupilData.find(index) == leftPupilData.end() || rightPupilData.find(index) == rightPupilData.end()) {
            missingPupilDataCount++;
            cout << index << "\tMISSING\tMISSING\tMISSING\tMISSING\n";
            continue;
        }

        PupilData leftActual = leftPupilData[index];
        PupilData rightActual = rightPupilData[index];

        // Get expected values from closest luminance in mapping (using luminance AFTER)
        PupilData leftExpected = getClosestLuminanceMatch(leftLuminanceMapping, leftActual.luminance);
        PupilData rightExpected = getClosestLuminanceMatch(rightLuminanceMapping, rightActual.luminance);

        // Compute t-test for left and right pupil sizes
        double leftPValue = computeTTest(leftActual.avgSize, leftActual.stdDev, leftActual.count,
                                         leftExpected.avgSize, leftExpected.stdDev, leftExpected.count);

        double rightPValue = computeTTest(rightActual.avgSize, rightActual.stdDev, rightActual.count,
                                          rightExpected.avgSize, rightExpected.stdDev, rightExpected.count);

        // Print results
        cout << index << "\t";
        if (leftPValue == -1) cout << "N/A\tN/A\t";
        else {
            cout << leftPValue << "\t";
            if (leftPValue < alpha) {
                cout << "Reject ✅\t";
                leftPass++;
            } else {
                cout << "Fail ❌\t";
            }
            totalLeft++;
        }

        if (rightPValue == -1) cout << "N/A\tN/A\n";
        else {
            cout << rightPValue << "\t";
            if (rightPValue < alpha) {
                cout << "Reject ✅\n";
                rightPass++;
            } else {
                cout << "Fail ❌\n";
            }
            totalRight++;
        }
    }

    // Summary
    cout << "\n==== Summary ====\n";
    cout << "Significance Level: " << alpha << '\n';
    cout << "Left Passed: " << leftPass << " / " << totalLeft << " (" << (totalLeft ? (leftPass * 100.0 / totalLeft) : 0) << "%)\n";
    cout << "Right Passed: " << rightPass << " / " << totalRight << " (" << (totalRight ? (rightPass * 100.0 / totalRight) : 0) << "%)\n";
    cout << "Missing Luminance Mapping: " << missingLuminanceMappingCount << "\n";
    cout << "Missing Pupil Data: " << missingPupilDataCount << "\n";
    cout << "Processing complete.\n";

    return 0;
}