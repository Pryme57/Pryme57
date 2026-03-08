use std::collections::HashMap;

// Custom error type using thiserror pattern
#[derive(Debug)]
enum AppError {
    NotFound(String),
    InvalidInput(String),
}

impl std::fmt::Display for AppError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AppError::NotFound(msg) => write!(f, "Not found: {}", msg),
            AppError::InvalidInput(msg) => write!(f, "Invalid input: {}", msg),
        }
    }
}

// A simple struct with methods
#[derive(Debug)]
struct Student {
    name: String,
    grades: Vec<f64>,
}

impl Student {
    fn new(name: &str) -> Self {
        Student {
            name: name.to_string(),
            grades: Vec::new(),
        }
    }

    fn add_grade(&mut self, grade: f64) -> Result<(), AppError> {
        if grade < 0.0 || grade > 100.0 {
            return Err(AppError::InvalidInput(format!(
                "Grade {} is out of range (0-100)",
                grade
            )));
        }
        self.grades.push(grade);
        Ok(())
    }

    fn average(&self) -> Option<f64> {
        if self.grades.is_empty() {
            return None;
        }
        Some(self.grades.iter().sum::<f64>() / self.grades.len() as f64)
    }

    fn letter_grade(&self) -> Result<char, AppError> {
        let avg = self
            .average()
            .ok_or_else(|| AppError::NotFound("No grades recorded".to_string()))?;

        Ok(match avg as u32 {
            90..=100 => 'A',
            80..=89 => 'B',
            70..=79 => 'C',
            60..=69 => 'D',
            _ => 'F',
        })
    }
}

// Generic function: works with any type that implements Display + PartialOrd
fn find_max<T: PartialOrd + std::fmt::Display>(items: &[T]) -> Option<&T> {
    items.iter().reduce(|a, b| if b > a { b } else { a })
}

// Trait example
trait Summarize {
    fn summary(&self) -> String;
}

impl Summarize for Student {
    fn summary(&self) -> String {
        match self.average() {
            Some(avg) => format!("{}: avg {:.1}", self.name, avg),
            None => format!("{}: no grades yet", self.name),
        }
    }
}

fn main() {
    println!("=== Rust Exploration ===\n");

    // Ownership & borrowing
    let mut students: HashMap<String, Student> = HashMap::new();

    let mut alice = Student::new("Alice");
    let grades = vec![92.0, 88.5, 95.0, 91.0];
    for g in grades {
        alice.add_grade(g).expect("Valid grade");
    }

    let mut bob = Student::new("Bob");
    for g in [74.0, 68.5, 81.0, 77.5] {
        bob.add_grade(g).expect("Valid grade");
    }

    // Test error handling
    match bob.add_grade(150.0) {
        Err(e) => println!("Expected error: {}", e),
        Ok(_) => {}
    }

    students.insert("alice".to_string(), alice);
    students.insert("bob".to_string(), bob);

    // Iterators & closures
    println!("Student summaries:");
    let mut names: Vec<&String> = students.keys().collect();
    names.sort();
    for name in &names {
        let student = &students[*name];
        println!("  - {}", student.summary());
        if let Ok(letter) = student.letter_grade() {
            println!("    Letter grade: {}", letter);
        }
    }

    // Generics
    let scores = vec![88.0, 95.5, 72.3, 99.1, 84.0];
    println!("\nHighest score: {}", find_max(&scores).unwrap());

    let words = vec!["banana", "apple", "cherry", "date"];
    println!("Last word alphabetically: {}", find_max(&words).unwrap());

    // Pattern matching with enums
    println!("\nGrade breakdown:");
    for name in &names {
        let student = &students[*name];
        match student.letter_grade() {
            Ok(g) => println!("  {} -> {}", name, g),
            Err(AppError::NotFound(msg)) => println!("  {}: {}", name, msg),
            Err(e) => println!("  Error: {}", e),
        }
    }

    println!("\nDone!");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_average() {
        let mut s = Student::new("Test");
        s.add_grade(80.0).unwrap();
        s.add_grade(90.0).unwrap();
        assert_eq!(s.average(), Some(85.0));
    }

    #[test]
    fn test_invalid_grade() {
        let mut s = Student::new("Test");
        assert!(s.add_grade(101.0).is_err());
        assert!(s.add_grade(-1.0).is_err());
    }

    #[test]
    fn test_letter_grade() {
        let mut s = Student::new("Test");
        s.add_grade(93.0).unwrap();
        assert_eq!(s.letter_grade().unwrap(), 'A');
    }

    #[test]
    fn test_no_grades() {
        let s = Student::new("Test");
        assert_eq!(s.average(), None);
        assert!(s.letter_grade().is_err());
    }

    #[test]
    fn test_find_max() {
        assert_eq!(find_max(&[3, 1, 4, 1, 5, 9, 2, 6]), Some(&9));
        assert_eq!(find_max::<i32>(&[]), None);
    }
}
