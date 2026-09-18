using System.Windows;
using WanwanDesktop.Models;

namespace WanwanDesktop.Windows;

public partial class HistoryWindow : Window
{
    public HistoryWindow(IReadOnlyList<ConversationHistoryItem> items)
    {
        InitializeComponent();

        // 窗口只绑定调用方已经读取好的快照，避免界面层直接访问文件系统。
        HistoryList.ItemsSource = items;
        EmptyLabel.Visibility = items.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        HistoryList.Visibility = items.Count == 0 ? Visibility.Collapsed : Visibility.Visible;
    }

    private void Close_Click(object sender, RoutedEventArgs e) => Close();
}
